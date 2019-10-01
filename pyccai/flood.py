import math
import os
import sys
from typing import Dict, List, Iterable, Set, Callable, Any

import ujson as json
from PIL import Image
from geopy.distance import geodesic

from pyccai.profiling import Profiler

LAT, LNG, ALT, RES = 0, 1, 2, 3

KILOMETER = 1000
DEMI_KM_HYPOTHENUS = (KILOMETER) * math.sqrt(2) / 2
DEMI_KM_HYPOTHENUS_GEODESIC = geodesic(meters=DEMI_KM_HYPOTHENUS)
DEMI_KILOMETER_GEODESIC = geodesic(meters=KILOMETER / 2)
FULL_KILOMETER_GEODESIC = geodesic(meters=KILOMETER)

ANGLE_WEST = -90
ANGLE_NORTH = 0
ANGLE_EAST = 90
ANGLE_SOUTH = 180

RED = (255, 0, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)


def pixel_is_blue(pixel):
    return pixel[2] > pixel[0] and pixel[2] > pixel[1]


class MapImage:
    __slots__ = 'width', 'height', 'pixels'

    def __init__(self, path):
        image = Image.open(path)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        width, height = image.size
        self.width = width
        self.height = height
        self.pixels = list(image.getdata())


class Point:
    __slots__ = ('lat', 'lng', 'alt', 'neighbors')

    def __init__(self, lat, lng, alt):
        self.lat = lat
        self.lng = lng
        self.alt = alt
        self.neighbors = {}

    @property
    def position(self):
        return self.lat, self.lng

    def __hash__(self):
        return hash(self.position)

    def __eq__(self, other):
        return self.position == other.position

    def __lt__(self, other):
        return self.position < other.position

    def __str__(self):
        return str(self.position)

    def __repr__(self):
        return str(self)

    def connect(self, point, weight):
        # type: (Point, float) -> None
        self.neighbors[point] = weight
        point.neighbors[self] = weight


class Bounds:
    __slots__ = ('north', 'south', 'east', 'west', 'nb_points')
    north: float
    south: float
    east: float
    west: float

    def __init__(self, points):
        # type: (List[Point]) -> None
        self.north = max(pt.lat for pt in points)
        self.south = min(pt.lat for pt in points)
        self.west = min(pt.lng for pt in points)
        self.east = max(pt.lng for pt in points)
        self.nb_points = len(points)

    def to_json(self):
        return [self.north, self.south, self.west, self.east]

    @property
    def north_west(self):
        return self.north, self.west

    @property
    def north_east(self):
        return self.north, self.east

    @property
    def south_west(self):
        return self.south, self.west

    @property
    def south_east(self):
        return self.south, self.east

    @property
    def width(self):
        return max(geodesic(self.north_west, self.north_east).meters,
                   geodesic(self.south_west, self.south_east).meters)

    @property
    def height(self):
        return max(geodesic(self.north_west, self.south_west).meters,
                   geodesic(self.north_east, self.south_east).meters)

    def __str__(self):
        return 'Rectangle(north_west=%s, nb=%d, width=%s, height=%s)' % (
            self.north_west,
            self.nb_points,
            self.width,
            self.height
        )

    def __repr__(self):
        return str(self)


class Cases:
    D, C, CD, B, BD, BC, BCD, A, AD, AC, ACD, AB, ABD, ABC, ABCD = tuple(range(1, 16))
    strings = [None, 'D', 'C', 'CD', 'B', 'BD', 'BC', 'BCD', 'A', 'AD', 'AC', 'ACD', 'AB', 'ABD',
               'ABC', 'ABCD']


class Coordinates:
    __slots__ = ('map_north', 'map_south', 'map_west', 'map_east', 'coordinates')

    def __init__(self, points):
        # type: (Iterable[Point]) -> None
        self.map_north = None
        self.map_south = None
        self.map_west = None
        self.map_east = None
        lat_to_points = {}  # type: Dict[float, List[Point]]

        for i, point in enumerate(points):
            if i == 0:
                self.map_north = self.map_south = point.lat
                self.map_west = self.map_east = point.lng
            else:
                if self.map_north < point.lat:
                    self.map_north = point.lat
                if self.map_south > point.lat:
                    self.map_south = point.lat
                if self.map_west > point.lng:
                    self.map_west = point.lng
                if self.map_east < point.lng:
                    self.map_east = point.lng
            lat_to_points.setdefault(point.lat, []).append(point)
        for lat in lat_to_points:
            lat_to_points[lat].sort()
        self.coordinates = [lat_to_points[lat] for lat in sorted(lat_to_points)]


def isolate_groups(points):
    # type: (Iterable[Point]) -> List[Set[Point]]
    points = set(points)
    groups = []
    while points:
        point = points.pop()
        neighbors = list(point.neighbors)
        group = {point}
        while neighbors:
            neighbor = neighbors.pop()
            if neighbor not in group:
                group.add(neighbor)
                if neighbor in points:
                    neighbors.extend(neighbor.neighbors)
                    points.remove(neighbor)
        groups.append(group)
    return groups


def in_rectangle(lat, lng, north, south, west, east):
    # type: (float, float, float, float, float, float) -> bool
    # lat increases from bottom to top
    # lng increases from left to right
    return south <= lat <= north and west <= lng <= east


def select_rectangle_centers(points):
    # type: (Iterable[Point]) -> List[Bounds]
    centers = []
    points = list(points)
    print('Group with', len(points), 'point(s)')
    while points:
        point = points.pop()
        top = DEMI_KILOMETER_GEODESIC.destination(point.position, 0)
        right = DEMI_KILOMETER_GEODESIC.destination(point.position, 90)
        bottom = DEMI_KILOMETER_GEODESIC.destination(point.position, 180)
        left = DEMI_KILOMETER_GEODESIC.destination(point.position, -90)
        north = top.latitude
        south = bottom.latitude
        west = left.longitude
        east = right.longitude
        group = [point]
        new_points = []
        for neighbor in points:
            if in_rectangle(neighbor.lat, neighbor.lng, north, south, west, east):
                group.append(neighbor)
            else:
                new_points.append(neighbor)
        bounds = Bounds(group)
        points = new_points
        centers.append(bounds)
        if points:
            print('\tremaining', len(points))
    return centers


def find_position(sorted_array, value, getter, left=None):
    # type: (List, Any, Callable[[List, int], Any], bool) -> int
    if left is True and value < getter(sorted_array, 0) and left:
        return -1
    if left is False and getter(sorted_array, -1) < value:
        return -1

    a = 0
    b = len(sorted_array) - 1
    c = None
    side = None
    while a <= b:
        c = int((a + b) / 2)
        current = getter(sorted_array, c)
        if current == value:
            return c
        if current < value:
            a = c + 1
            side = 1
        else:
            b = c - 1
            side = -1
    if left is None:
        return -1
    if left and side < 0:
        c = c - 1
    elif not left and side > 0:
        c = c + 1
        if c == len(sorted_array):
            c = -1
    return c


def get_latitude(coordinates, position):
    # type: (List[List[Point]], int) -> float
    return coordinates[position][0].lat


def get_longitude(points, position):
    # type: (List[Point], int) -> float
    return points[position].lng


def get_points_in_rectangle(coordinates, north, south, west, east):
    # type: (List[List[Point]], float, float, float, float) -> List[Point]
    points = []
    position_south = find_position(coordinates, south, get_latitude, left=False)
    position_north = find_position(coordinates, north, get_latitude, left=True)
    if position_south < 0 or position_north < 0:
        return points
    for i in range(position_south, position_north + 1):
        position_west = find_position(coordinates[i], west, get_longitude, left=False)
        position_east = find_position(coordinates[i], east, get_longitude, left=True)
        if position_west < 0 or position_east < 0:
            continue
        points.extend(coordinates[i][j] for j in range(position_west, position_east + 1))
    return points


def get_neighbors(point, coords, in_map=False):
    # type: (Point, Coordinates, bool) -> List[Point]
    # Compute bounds of rectangles centered on point with 1 Km side.
    # north_east = DEMI_KILOMETER_GEODESIC.destination(point.position, 45)
    # south_west = DEMI_KILOMETER_GEODESIC.destination(point.position, 180 + 45)
    # north = north_east.latitude
    # south = south_west.latitude
    # west = south_west.longitude
    # east = north_east.longitude
    north = DEMI_KILOMETER_GEODESIC.destination(point.position, 0).latitude
    south = DEMI_KILOMETER_GEODESIC.destination(point.position, 180).latitude
    west = DEMI_KILOMETER_GEODESIC.destination(point.position, -90).longitude
    east = DEMI_KILOMETER_GEODESIC.destination(point.position, 90).longitude
    if in_map:
        # A---B
        # |   |
        # D---C
        a_in = in_rectangle(
            north, west, coords.map_north, coords.map_south, coords.map_west, coords.map_east)
        b_in = in_rectangle(
            north, east, coords.map_north, coords.map_south, coords.map_west, coords.map_east)
        c_in = in_rectangle(
            south, east, coords.map_north, coords.map_south, coords.map_west, coords.map_east)
        d_in = in_rectangle(
            south, west, coords.map_north, coords.map_south, coords.map_west, coords.map_east)
        case = a_in * 8 + b_in * 4 + c_in * 2 + d_in
        if case != Cases.ABCD:
            if case == Cases.A:
                south = coords.map_south
                east = coords.map_east
                north = FULL_KILOMETER_GEODESIC.destination((south, east), 0).latitude
                west = FULL_KILOMETER_GEODESIC.destination((south, east), -90).longitude
            elif case == Cases.B:
                south = coords.map_south
                west = coords.map_west
                north = FULL_KILOMETER_GEODESIC.destination((south, west), 0).latitude
                east = FULL_KILOMETER_GEODESIC.destination((south, west), 90).longitude
            elif case == Cases.C:
                north = coords.map_north
                west = coords.map_west
                south = FULL_KILOMETER_GEODESIC.destination((north, west), 180).latitude
                east = FULL_KILOMETER_GEODESIC.destination((north, west), 90).longitude
            elif case == Cases.D:
                north = coords.map_north
                east = coords.map_east
                west = FULL_KILOMETER_GEODESIC.destination((north, east), -90).longitude
                south = FULL_KILOMETER_GEODESIC.destination((north, east), 180).latitude
            elif case == Cases.AB:
                south = coords.map_south
                north = FULL_KILOMETER_GEODESIC.destination((south, west), 0).latitude
            elif case == Cases.CD:
                north = coords.map_north
                south = FULL_KILOMETER_GEODESIC.destination((north, west), 180).latitude
            elif case == Cases.AD:
                east = coords.map_east
                west = FULL_KILOMETER_GEODESIC.destination((north, east), -90).longitude
            elif case == Cases.BC:
                west = coords.map_west
                east = FULL_KILOMETER_GEODESIC.destination((north, west), 90).longitude
            else:
                is_error = True
                if case == 0:
                    # map_a_in = in_rectangle(coords.map_north, coords.map_west, north, south, west, east)
                    # map_b_in = in_rectangle(coords.map_north, coords.map_east, north, south, west, east)
                    # map_c_in = in_rectangle(coords.map_south, coords.map_east, north, south, west, east)
                    # map_d_in = in_rectangle(coords.map_south, coords.map_west, north, south, west, east)
                    # map_case = map_a_in * 8 + map_b_in * 4 + map_c_in * 2 + map_d_in
                    # is_error = map_case not in (Cases.A, Cases.B, Cases.C, Cases.D, Cases.AB, Cases.CD, Cases.AD, Cases.BC)
                    is_error = False
                if is_error:
                    print('Point', point.position)
                    print('Rect_', north, south, west, east)
                    print('Map__', coords.map_north, coords.map_south, coords.map_west, coords.map_east)
                    raise RuntimeError('Impossible case %s' % Cases.strings[case])
    # Get points in rectangle.
    return get_points_in_rectangle(coords.coordinates, north, south, west, east)


def main():
    if len(sys.argv) != 4:
        print('Usage: python flood.py <map-file-name> <flood-threshold> <output-name>')
        exit(-1)
    map_file_name = sys.argv[1]
    flood_threshold = float(sys.argv[2])
    output_name = sys.argv[3]
    map_title = os.path.splitext(os.path.basename(map_file_name))[0]
    map_image_path = '%s.png' % map_title

    image = None
    if os.path.isfile(map_image_path):
        image = MapImage(map_image_path)

    flood = []  # type: List[Point]
    print('Loading map ...')
    debug_step = 2000000
    with open(map_file_name) as file:
        iterator_lines = iter(file)
        pieces = next(iterator_lines).strip().split()
        width = int(pieces[1])
        height = int(pieces[2])
        size = int(pieces[3])
        with Profiler('select flooded points.'):
            for index_line, line in enumerate(iterator_lines):
                pieces = line.strip().split()
                alt = float(pieces[ALT])
                if alt <= flood_threshold:
                    if image:
                        # skip water
                        map_x = index_line % width
                        map_y = index_line // width
                        img_x = round(map_x * (image.width - 1) / (width - 1))
                        img_y = round(map_y * (image.height - 1) / (height - 1))
                        img_index = img_y * image.height + img_x
                        if pixel_is_blue(image.pixels[img_index]):
                            continue
                    flood.append(Point(float(pieces[LAT]), float(pieces[LNG]), alt))
                if (index_line + 1) % debug_step == 0:
                    print('Loaded line', index_line + 1, '/', size)
    assert (index_line + 1) == size == width * height
    print('Finished loading map.')

    print('Got', len(flood), 'flooded points /', size, 'with threshold', flood_threshold,
          '(%s %%)' % (len(flood) * 100 / size))

    rectangles = []
    points = set(flood)
    with Profiler('Group flooded points in rectangle (very approximate algorithm)'):
        while points:
            print('Remaining', len(points), 'point(s).')
            coordinates = Coordinates(points)
            point = max(points)
            neighbors = get_neighbors(point, coordinates, True)
            points.difference_update(neighbors)
            if len(neighbors) == 1:
                continue
            bounds = Bounds(neighbors)
            if bounds.width < 10 or bounds.height < 10:
                continue
            rectangles.append(bounds)
    print('Found', len(rectangles), 'rectangle(s) for', len(flood), 'point(s).')
    print(min(r.nb_points for r in rectangles), max(r.nb_points for r in rectangles))

    output_file_name = '%s.js' % output_name
    with open(output_file_name, 'w') as file:
        file.write('export const FLOOD = %s;' % json.dumps([r.to_json() for r in rectangles]))
    print('Output into', output_file_name)


if __name__ == '__main__':
    main()
