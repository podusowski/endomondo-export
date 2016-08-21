import requests
import uuid
import socket
import datetime
import pytz

SPORTS = {
    0:  'Running',
    1:  'Cycling, transport',
    2:  'Cycling, sport',
    3:  'Mountain biking',
    4:  'Skating',
    5:  'Roller skiing',
    6:  'Skiing, cross country',
    7:  'Skiing, downhill',
    8:  'Snowboarding',
    9:  'Kayaking',
    10: 'Kite surfing',
    11: 'Rowing',
    12: 'Sailing',
    13: 'Windsurfing',
    14: 'Fitness walking',
    15: 'Golfing',
    16: 'Hiking',
    17: 'Orienteering',
    18: 'Walking',
    19: 'Riding',
    20: 'Swimming',
    21: 'Spinning',
    22: 'Other',
    23: 'Aerobics',
    24: 'Badminton',
    25: 'Baseball',
    26: 'Basketball',
    27: 'Boxing',
    28: 'Climbing stairs',
    29: 'Cricket',
    30: 'Cross training',
    31: 'Dancing',
    32: 'Fencing',
    33: 'Football, American',
    34: 'Football, rugby',
    35: 'Football, soccer',
    36: 'Handball',
    37: 'Hockey',
    38: 'Pilates',
    39: 'Polo',
    40: 'Scuba diving',
    41: 'Squash',
    42: 'Table tennis',
    43: 'Tennis',
    44: 'Volleyball, beach',
    45: 'Volleyball, indoor',
    46: 'Weight training',
    47: 'Yoga',
    48: 'Martial arts',
    49: 'Gymnastics',
    50: 'Step counter'
}


class Protocol:
    os = "Android"
    os_version = "2.2"
    model = "M"
    user_agent = "Dalvik/1.4.0 (Linux; U; %s %s; %s Build/GRI54)" % (os, os_version, model)
    device_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, socket.gethostname()))

    def __init__(self, email=None, password=None, token=None):
        self.auth_token = token
        self.request = requests.session()
        self.request.headers['User-Agent'] = self.user_agent

        if self.auth_token is None:
            self.auth_token = self._request_auth_token(email, password)

    def _request_auth_token(self, email, password):
        params = {'email':       email,
                  'password':    password,
                  'country':     'US',
                  'deviceId':    self.device_id,
                  'os':          self.os,
                  'appVersion':  "7.1",
                  'appVariant':  "M-Pro",
                  'osVersion':   self.os_version,
                  'model':       self.model,
                  'v':           2.4,
                  'action':      'PAIR'}

        r = self._simple_call('auth', params)

        for line in self._parse_text(r):
            key, value = line.split("=")
            if key == "authToken":
                return value

        return None

    def _parse_text(self, response):
        lines = response.text.split("\n")

        if len(lines) < 1:
            raise ValueError("Error: URL %s: empty response" % response.url)

        if lines[0] != "OK":
            raise ValueError("Error: URL %s: %s" % (response.url, lines[0]))

        return lines[1:]

    def _parse_json(self, response):
        return response.json()['data']

    def _simple_call(self, command, params):
        r = self.request.get('http://api.mobile.endomondo.com/mobile/' + command, params=params)

        if r.status_code != requests.codes.ok:
            r.raise_for_status()
            return None

        return r

    def call(self, url, format, params={}):
        params.update({'authToken': self.auth_token,
                       'language': 'EN'})

        r = self._simple_call(url, params)

        if format == 'text':
            return self._parse_text(r)

        if format == 'json':
            return self._parse_json(r)

        return r


def _to_endomondo_time(time):
    return time.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _to_python_time(endomondo_time):
    return datetime.datetime.strptime(endomondo_time, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=pytz.utc)


class Endomondo:
    def __init__(self, email=None, password=None, token=None):
        self.protocol = Protocol(email, password, token)
        self.auth_token = self.protocol.auth_token

    def get_workouts(self, max_results=40, after=None):
        params = {'maxResults': max_results}

        if after is not None:
            params.update({'after': _to_endomondo_time(after)})

        json = self.protocol.call('api/workout/list', 'json', params)

        return [Workout(self.protocol, w) for w in json]


class Workout:
    def __init__(self, protocol, properties):
        self.protocol = protocol
        self.properties = properties
        self.id = self.properties['id']

    def __repr__(self):
        return "#{} - {}".format(self.id, self.sport)

    @property
    def sport(self):
        sport = int(self.properties['sport'])
        return SPORTS.get(sport, "Other")

    @property
    def points(self):
        return self._fetch_points()

    def _fetch_points(self):
        lines = self.protocol.call('readTrack', 'text', {'trackId': self.id})

        def to_float(v):
            if v == '' or v is None:
                return None
            return float(v)

        def trackpoint(csv):
            data = csv.split(';')
            if len(data) < 9:
                return None
            else:
                return {'time': _to_python_time(data[0]),
                        'lat': to_float(data[2]),
                        'lon': to_float(data[3]),
                        'alt': to_float(data[6]),
                        'hr': to_float(data[7])}

        return list(filter(lambda x: x is not None, map(trackpoint, lines[1:])))
