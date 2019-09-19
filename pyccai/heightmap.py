import argparse
import multiprocessing
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import List, Tuple, Union, Optional

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


def _get_url_along_path(from_pos, to_pos, n_samples):
    from_lat, from_lng = from_pos
    to_lat, to_lng = to_pos
    return '%s?%s' % (ELEVATION_BASE_URL, urllib.parse.urlencode({
        'path': '%s,%s|%s,%s' % (from_lat, from_lng, to_lat, to_lng),
        'samples': n_samples,
        'key': API_KEY
    }))


def _get_elevations_along_path(parameters):
    # type: (Tuple[str, int, Optional[int]]) -> Union[List, Tuple[int, List]]
    url, n_samples, number = parameters
    with urllib.request.urlopen(url) as response:
        decoded_response = json.loads(response.read().decode())
    if decoded_response['status'] != 'OK':
        raise RuntimeError(decoded_response['status'])
    if len(decoded_response['results']) != n_samples:
        raise RuntimeError('INVALID_RESPONSE_LENGTH')
    output = [(res['elevation'], res['resolution']) for res in decoded_response['results']]
    del decoded_response
    if number is None:
        return output
    if number % 100 == 0:
        print('Query', number + 1)
    return number, output


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
    parser = argparse.ArgumentParser(
        prog='Generate height map (grayscale image) for a rectangle based on '
             'north-west and south-east coordinates.',
        description='Given north-west and south-east coordinates, the script will '
                    'sample points in corresponding geographical rectangle, '
                    'retrieve altitude for sampled points, '
                    'and save it in a grayscale image. '
                    'Google elevation API is used to get elevation data.'
    )
    parser.add_argument('nw_lat', type=float,
                        help='North-west latitude')
    parser.add_argument('nw_lng', type=float,
                        help='North-west longitude')
    parser.add_argument('se_lat', type=float,
                        help='South-east latitude')
    parser.add_argument('se_lng', type=float,
                        help='South-east longitutde')
    parser.add_argument('--output', '-o', type=str, default='output.png',
                        help='Output file name (default: "output.png")')
    parser.add_argument('--resolution', '-r', type=float, default=10,
                        help='resolution (in meters) to use to sample rectangle. '
                             'Default is 10 meters. For example, if rectangle size is 1 x 1 Km '
                             'and resolution is 10m, then rectangle will be sampled in each 10m '
                             'to comppute (1000/10 + 1) = 101 points in width, and same in height. '
                             'Output image will then have 101 x 101 = 10201 pixels.')
    parser.add_argument('--compute-only', '-c', action='store_true',
                        help='If specified, script will just compute and display '
                             'number of sampled points without generating anything.')
    parser.add_argument('--estimate', '-e', type=int, default=0,
                        help='A number of points for which to compute estimated time '
                             'to retrieve elevation data. If specified (and not with compute-only), '
                             'then script will estimate and display time necessary '
                             'to get elevation data for this number of points, **after** having '
                             'actually generating the height map for given coordinates. '
                             'This may be useful to estimate computation time before computing '
                             'higher height maps.')
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
    print('Width', lng_diff_meters, 'meters')
    print('Height', lat_diff_meters, 'meters')
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

    cpu_count = os.cpu_count()
    nb_processes = max(int(3 * cpu_count / 4), 2)
    print('Getting elevation for', width, 'x', height, '=', nb_points, 'points using', len(queries),
          'queries in', nb_processes, '/', cpu_count, 'processes.')
    if args.compute_only:
        return

    tasks = [
        (_get_url_along_path(*query), query[-1], number)
        for number, query in enumerate(queries)
    ]

    time_start = datetime.now()
    with multiprocessing.Pool(processes=nb_processes) as pool:
        pool_results = pool.imap_unordered(_get_elevations_along_path, tasks, chunksize=10)
        pool_results = list(pool_results)
    time_end = datetime.now()

    profile = Profile(time_start, time_end)
    print('Got elevations', profile, 'for', nb_points, 'points.')
    if args.estimate > 0:
        estimation = (args.estimate * profile.total_microseconds / nb_points)
        print('Estimated time:', Profile(0, estimation), 'for', args.estimate, 'points.')

    results = []
    pool_results.sort(key=lambda val: val[0])
    for pool_result in pool_results:
        results.extend(pool_result[1])
    min_resolution = None
    max_resolution = None
    min_elevation = None
    max_elevation = None
    elevations = []
    for result in results:
        elevation, resolution = result
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
