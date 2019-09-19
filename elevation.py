import argparse
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import List, Tuple

import ujson as json
from PIL import Image
from geopy.distance import geodesic

ELEVATION_BASE_URL = 'https://maps.googleapis.com/maps/api/elevation/json'
API_KEY = 'AIzaSyAMXLOTP3THijZgZGwmoyXvYMNf_a9jF4Y'
BATCH_SIZE = 512


class Profile(object):
    __slots__ = ('seconds', 'microseconds')

    def __init__(self, time_start, time_end):
        difference = time_end - time_start
        if isinstance(difference, timedelta):
            self.seconds = difference.seconds + difference.days * 24 * 3600
            self.microseconds = difference.microseconds
        else:
            self.seconds = difference // 1000000
            self.microseconds = difference % 1000000

    @property
    def total_microseconds(self):
        return self.seconds * 1000000 + self.microseconds

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


def _get_elevations_along_path(from_pos, to_pos, n_samples):
    # type: (Tuple[float, float], Tuple[float, float], int) -> List
    from_lat, from_lng = from_pos
    to_lat, to_lng = to_pos
    parameters = {
        'path': '%s,%s|%s,%s' % (from_lat, from_lng, to_lat, to_lng),
        'samples': n_samples,
        'key': API_KEY
    }
    data = urllib.parse.urlencode(parameters)
    url = '%s?%s' % (ELEVATION_BASE_URL, data)
    with urllib.request.urlopen(url) as response:
        decoded_response = json.loads(response.read().decode())
    if decoded_response['status'] != 'OK':
        raise RuntimeError(decoded_response['status'])
    if len(decoded_response['results']) != n_samples:
        raise RuntimeError('INVALID_RESPONSE_LENGTH')
    return decoded_response['results']


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
    parser.add_argument('--output', '-o', type=str, default='output.png')
    parser.add_argument('--resolution', '-r', type=float, default=10)
    parser.add_argument('--compute-only', '-c', action='store_true')
    parser.add_argument('--estimate', '-e', type=int, default=0)
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

    lat_diff_meters = geodesic((nw_lat, nw_lng), (sw_lat, sw_lng)).meters
    lng_diff_meters = geodesic((nw_lat, nw_lng), (ne_lat, ne_lng)).meters
    nb_div_lat = round(lat_diff_meters / resolution)
    nb_div_lng = round(lng_diff_meters / resolution)
    lat_gap_degrees = abs(sw_lat - nw_lat)
    lng_gap_degrees = abs(se_lng - sw_lng)
    lat_step_degrees = -(lat_gap_degrees / nb_div_lat)
    lng_step_degrees = lng_gap_degrees / nb_div_lng
    width = nb_div_lng + 1
    height = nb_div_lat + 1
    nb_points = width * height
    points_left = [(nw_lat, nw_lng)]
    points_right = [(ne_lat, ne_lng)]
    queries = []
    for i in range(1, height):
        prev_left = points_left[-1]
        prev_right = points_right[-1]
        points_left.append((prev_left[0] + lat_step_degrees, prev_left[1]))
        points_right.append((prev_right[0] + lat_step_degrees, prev_right[1]))
    for i in range(height):
        left = points_left[i]
        cursor = 0
        while cursor < width:
            end = min(cursor + BATCH_SIZE, width)
            length = end - cursor
            step = lng_step_degrees * (length - 1)
            local_right = (left[0], left[1] + step)
            queries.append((left, local_right, length))
            left = (local_right[0], local_right[1] + lng_step_degrees)
            cursor = end

    sum_queries = 0
    for query in queries:
        length = query[2]
        assert length > 1
        sum_queries += length
    assert sum_queries == nb_points

    print('Getting elevation for', width, 'x', height, '=', nb_points, 'points using', len(queries), 'queries.')
    if args.compute_only:
        return

    results = []
    total = 0
    time_start = datetime.now()
    for query in queries:
        results.extend(_get_elevations_along_path(*query))
        total += query[-1]
        print('...', total, '/', nb_points)
    time_end = datetime.now()
    profile = Profile(time_start, time_end)
    print('Got elevations', profile, 'for', nb_points, 'points.')
    if args.estimate > 0:
        estimation = (args.estimate * profile.total_microseconds / nb_points)
        print('Estimated time:', Profile(0, estimation), 'for', args.estimate, 'points.')

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
    output_image = Image.new(mode='L', size=(width, height), color=0)
    if min_elevation != max_elevation:
        output_image.putdata([
            int(255 * (elevation - min_elevation) / (max_elevation - min_elevation))
            for elevation in elevations])
    output_image.save(args.output)


if __name__ == '__main__':
    main()
