import argparse
import urllib.parse
import urllib.request
from typing import List, Tuple
from geopy.distance import geodesic
from datetime import datetime
import ujson as json
from PIL import Image

ELEVATION_BASE_URL = 'https://maps.googleapis.com/maps/api/elevation/json'
API_KEY = 'AIzaSyAMXLOTP3THijZgZGwmoyXvYMNf_a9jF4Y'

class Profile(object):
    __slots__ = ('seconds', 'microseconds')

    def __init__(self, time_start, time_end):
        difference = time_end - time_start
        self.seconds = difference.seconds + difference.days * 24 * 3600
        self.microseconds = difference.microseconds

    def __str__(self):
        hours = self.seconds // 3600
        minutes = (self.seconds - 3600 * hours) // 60
        seconds = (self.seconds - 3600 * hours - 60 * minutes)
        pieces = []
        if hours:
            pieces.append('%d h' % hours)
        if minutes:
            pieces.append('%d min' % minutes)
        if seconds:
            pieces.append('%d sec' % seconds)
        if self.microseconds:
            pieces.append('%d microsec' % self.microseconds)
        return '(%s)' % (' '.join(pieces) if pieces else '0 sec')


def _get_elevations(locations=()):
    # type: (List[Tuple[float, float]]) -> List
    if not locations:
        return []
    parameters = {
        'locations': '|'.join('%s,%s' % (lat, lng) for (lat, lng) in locations),
        'key': API_KEY
    }
    data = urllib.parse.urlencode(parameters)
    url = '%s?%s' % (ELEVATION_BASE_URL, data)
    with urllib.request.urlopen(url) as response:
        decoded_response = json.loads(response.read().decode())
    if decoded_response['status'] != 'OK':
        raise RuntimeError(decoded_response['status'])
    if len(decoded_response['results']) != len(locations):
        raise RuntimeError('INVALID_RESPONSE_LENGTH')
    return decoded_response['results']


def get_elevations(locations=()):
    # type: (List[Tuple[float, float]]) -> List
    batch_size = 350
    output = []
    cursor = 0
    nb_locations = len(locations)
    while cursor < nb_locations:
        print('Getting', cursor, 'to', cursor + batch_size, 'on', nb_locations)
        output.extend(_get_elevations(locations[cursor:(cursor + batch_size)]))
        cursor += batch_size
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('nw_lat', type=float)
    parser.add_argument('nw_lng', type=float)
    parser.add_argument('se_lat', type=float)
    parser.add_argument('se_lng', type=float)
    parser.add_argument('--output', '-o', type=str, required=True)
    parser.add_argument('--resolution', '-r', type=float, default=10)
    parser.add_argument('--compute-only', '-c', action='store_true')
    args = parser.parse_args()

    resolution = args.resolution
    nw_lat = args.nw_lat
    nw_lng = args.nw_lng
    se_lat = args.se_lat
    se_lng = args.se_lng
    ne_lat = nw_lat
    ne_lng = se_lng
    sw_lat = se_lat
    sw_lng = nw_lng

    lat_distance = geodesic((nw_lat, nw_lng), (sw_lat, sw_lng)).meters
    lng_distance = geodesic((nw_lat, nw_lng), (ne_lat, ne_lng)).meters
    nb_div_lat = round(lat_distance / resolution)
    nb_div_lng = round(lng_distance / resolution)
    lat_gap = abs(sw_lat - nw_lat)
    lng_gap = abs(se_lng - sw_lng)
    lat_step = -(lat_gap / nb_div_lat)
    lng_step = lng_gap / nb_div_lng
    width = nb_div_lng + 1
    height = nb_div_lat + 1
    nb_points = width * height
    print('Computing', width, 'x', height, '=', nb_points, 'points')
    if args.compute_only:
        return

    locations = [(nw_lat, nw_lng)]
    for i in range(1, nb_points):
        previous_lat, previous_lng = locations[-1]
        lat = previous_lat + lat_step if i % width == 0 else previous_lat
        lng = nw_lng if i % width == 0 else previous_lng + lng_step
        locations.append((lat, lng))
    print('Computed', width, 'x', height, '=', len(locations), 'points')
    print('Latest point:   ', locations[-1])
    print('Latest expected:', (se_lat, se_lng))

    print('Getting elevations')
    time_start = datetime.now()
    results = get_elevations(locations)
    time_end = datetime.now()
    print('Got elevations', Profile(time_start, time_end))

    image_data = []
    min_resolution = None
    max_resolution = None
    min_elevation = None
    max_elevation = None
    elevations = []
    for result in results:
        elevation = result['elevation']
        resolution = result['resolution']
        if min_resolution is None or min_resolution > resolution:
            min_resolution = resolution
        if max_resolution is None or max_resolution < resolution:
            max_resolution = resolution
        if min_elevation is None or min_elevation > elevation:
            min_elevation = elevation
        if max_elevation is None or max_elevation < elevation:
            max_elevation = elevation
        elevations.append(elevation)
    if min_elevation == max_elevation:
        image_data = [0] * nb_points
    else:
        for elevation in elevations:
            image_data.append(
                int(255 * (elevation - min_elevation) / (max_elevation - min_elevation)))
    output_image = Image.new(mode='L', size=(width, height), color=0)
    output_image.putdata(image_data)
    output_image.save(args.output)


if __name__ == '__main__':
    main()
