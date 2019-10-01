import sys
import urllib.parse
import urllib.request

from geopy.distance import geodesic

from pyccai.flood import LAT, LNG
from pyccai.heightmap import API_KEY
from pyccai.profiling import Profiler

STATIC_MAP_BASE_URL = 'https://maps.googleapis.com/maps/api/staticmap'


# https://maps.googleapis.com/maps/api/staticmap?center=45.56327084282992%2C-73.70742061613984&zoom=15&size=4238x3680&scale=1&format=png32&style=feature%3Aall%7Celement%3Alabels%7Cvisibility%3Aoff&key=AIzaSyAMXLOTP3THijZgZGwmoyXvYMNf_a9jF4Y

def main():
    if len(sys.argv) != 3:
        return

    map_file_name = sys.argv[1]
    output_name = sys.argv[2]
    debug_step = 2000000
    map_north = None
    map_south = None
    map_east = None
    map_west = None

    with open(map_file_name) as file:
        iterator_lines = iter(file)
        pieces = next(iterator_lines).strip().split()
        size = int(pieces[3])
        with Profiler('select flooded points.'):
            for index_line, line in enumerate(iterator_lines):
                pieces = line.strip().split()
                lat = float(pieces[LAT])
                lng = float(pieces[LNG])
                if map_south is None or map_south > lat:
                    map_south = lat
                if map_north is None or map_north < lat:
                    map_north = lat
                if map_west is None or map_west > lng:
                    map_west = lng
                if map_east is None or map_east < lng:
                    map_east = lng
                if (index_line + 1) % debug_step == 0:
                    print('Loaded line', index_line + 1, '/', size)
        print(map_north)
        print(map_west, map_east)
        print(map_south)
        print()
        print('Width', geodesic((map_north, map_west), (map_north, map_east)).meters, 'meter(s)')
        print('Height', geodesic((map_north, map_west), (map_south, map_west)).meters, 'meter(s)')
        format = 'png32'
        styles = [
            'feature:all|element:labels|visibility:off',
            'feature:road|visibility:off',
            'feature:all|color:0xffff00',
            'feature:water|color:0x0000ff',
        ]
        render_width = render_height = 640
        parameters = {
            'size': '%dx%d' % (render_width, render_height),
            'format': format,
            'key': API_KEY,
        }
        url = '%s?%s' % (STATIC_MAP_BASE_URL, urllib.parse.urlencode(parameters))
        for style in styles:
            url += '&style=%s' % urllib.parse.quote(style)
        url += '&markers=anchor:topleft|icon:%s|%s,%s' % (
            'https://notoraptor.github.io/images/redpixel.png',
            map_north,
            map_west
        )
        url += '&markers=anchor:bottomright|icon:%s|%s,%s' % (
            'https://notoraptor.github.io/images/redpixel.png',
            map_south,
            map_east
        )

    print(urllib.parse.unquote(url))
    with urllib.request.urlopen(url) as response:
        decoded_response = response.read()
    with open('%s.png' % output_name, 'wb') as file:
        file.write(decoded_response)


if __name__ == '__main__':
    main()
