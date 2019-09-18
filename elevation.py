import argparse
import ujson as json
from PIL import Image
from urllib.parse import urlencode
from urllib.request import urlopen
from typing import List, Tuple

ELEVATION_BASE_URL = 'https://maps.googleapis.com/maps/api/elevation/json'
API_KEY = 'AIzaSyAMXLOTP3THijZgZGwmoyXvYMNf_a9jF4Y'
NB_DIVISIONS = 20
LEN_SIDE = NB_DIVISIONS + 1
NB_POINTS = LEN_SIDE * LEN_SIDE

def get_elevation(locations=()):
    # type: (List[Tuple[float, float]]) -> List
    parameters = {
        'locations': '|'.join('%s,%s' % (lat, lng) for (lat, lng) in locations),
        'key': API_KEY
    }
    url = '%s?%s' % (ELEVATION_BASE_URL, urlencode(parameters))
    print(len(url))
    response = json.loads(urlopen(url).read().decode())
    if response['status'] != 'OK':
        raise RuntimeError(response['status'])
    if len(response['results']) != len(locations):
        raise RuntimeError('INVALID_RESPONSE_LENGTH')
    return response['results']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('nw_lat', type=float)
    parser.add_argument('nw_lng', type=float)
    parser.add_argument('se_lat', type=float)
    parser.add_argument('se_lng', type=float)
    parser.add_argument('--output', '-o', type=str, required=True)
    args = parser.parse_args()
    nw_lat = args.nw_lat
    nw_lng = args.nw_lng
    se_lat = args.se_lat
    se_lng = args.se_lng
    ne_lat = nw_lat
    ne_lng = se_lng
    sw_lat = se_lat
    sw_lng = nw_lng
    lat_gap = abs(sw_lat - nw_lat)
    lng_gap = abs(se_lng - sw_lng)
    lat_step = -(lat_gap / NB_DIVISIONS)
    lng_step = lng_gap / NB_DIVISIONS
    locations = [(nw_lat, nw_lng)]
    for i in range(1, NB_POINTS):
        previous_lat, previous_lng = locations[-1]
        lat = previous_lat + lat_step if i % LEN_SIDE == 0 else previous_lat
        lng = nw_lng if i % LEN_SIDE == 0 else previous_lng + lng_step
        locations.append((lat, lng))
    print('Computed', LEN_SIDE, 'x', LEN_SIDE, '=', len(locations), 'points')
    print('Latest point:   ', locations[-1])
    print('Latest expected:', (se_lat, se_lng))
    results = get_elevation(locations)
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
        image_data = [0] * NB_POINTS
    else:
        for elevation in elevations:
            image_data.append(int(255 * (elevation - min_elevation) / (max_elevation - min_elevation)))
    output_image = Image.new(mode='L', size=(LEN_SIDE, LEN_SIDE), color=0)
    output_image.putdata(image_data)
    output_image.save(args.name)

if __name__ == '__main__':
    main()
