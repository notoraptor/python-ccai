import sys
import math
from typing import Dict, List, Iterable, Set, Union, Tuple, Callable, Any

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
    __slots__ = ('north', 'south', 'east', 'west', 'points')
    north: float
    south: float
    east: float
    west: float
    points: List[Point]

    def __init__(self, points):
        # type: (Iterable[Point]) -> None
        self.north = max(pt.lat for pt in points)
        self.south = min(pt.lat for pt in points)
        self.west = min(pt.lng for pt in points)
        self.east = max(pt.lng for pt in points)
        self.points = points if isinstance(points, list) else list(points)

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

    def __str__(self):
        return 'Rectangle(north_west=%s, nb=%d, width=%s, height=%s)' % (
            self.north_west,
            len(self.points),
            max(geodesic(self.north_west, self.north_east).meters,
                geodesic(self.south_west, self.south_east).meters),
            max(geodesic(self.north_west, self.south_west).meters,
                geodesic(self.north_east, self.south_east).meters)
        )

    def __repr__(self):
        return str(self)


class Cases:
    D, C, CD, B, BD, BC, BCD, A, AD, AC, ACD, AB, ABD, ABC, ABCD = tuple(range(1, 16))
    strings = [None, 'D', 'C', 'CD', 'B', 'BD', 'BC', 'BCD', 'A', 'AD', 'AC', 'ACD', 'AB', 'ABD',
               'ABC', 'ABCD']


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


def get_neighbors(point, coordinates, map_north, map_south, map_west, map_east, in_map=False):
    # type: (Point, List[List[Point]], float, float, float, float, bool) -> List[Point]
    # Compute bounds of rectangles centered on point with 1 Km side.
    north_east = DEMI_KILOMETER_GEODESIC.destination(point.position, 45)
    south_west = DEMI_KILOMETER_GEODESIC.destination(point.position, 180 + 45)
    north = north_east.latitude
    south = south_west.latitude
    west = south_west.longitude
    east = north_east.longitude
    # north = DEMI_KILOMETER_GEODESIC.destination(point.position, 0).latitude
    # south = DEMI_KILOMETER_GEODESIC.destination(point.position, 180).latitude
    # west = DEMI_KILOMETER_GEODESIC.destination(point.position, -90).longitude
    # east = DEMI_KILOMETER_GEODESIC.destination(point.position, 90).longitude
    if in_map:
        a_in = in_rectangle(north, west, map_north, map_south, map_west, map_east)
        b_in = in_rectangle(north, east, map_north, map_south, map_west, map_east)
        c_in = in_rectangle(south, east, map_north, map_south, map_west, map_east)
        d_in = in_rectangle(south, west, map_north, map_south, map_west, map_east)
        case = a_in * 8 + b_in * 4 + c_in * 2 + d_in
        if case != Cases.ABCD:
            if case == Cases.A:
                south = map_south
                east = map_east
                north = FULL_KILOMETER_GEODESIC.destination((south, east), 0).latitude
                west = FULL_KILOMETER_GEODESIC.destination((south, east), -90).longitude
            elif case == Cases.B:
                south = map_south
                west = map_west
                north = FULL_KILOMETER_GEODESIC.destination((south, west), 0).latitude
                east = FULL_KILOMETER_GEODESIC.destination((south, west), 90).longitude
            elif case == Cases.C:
                north = map_north
                west = map_west
                south = FULL_KILOMETER_GEODESIC.destination((north, west), 180).latitude
                east = FULL_KILOMETER_GEODESIC.destination((north, west), 90).longitude
            elif case == Cases.D:
                north = map_north
                east = map_east
                west = FULL_KILOMETER_GEODESIC.destination((north, east), -90).longitude
                south = FULL_KILOMETER_GEODESIC.destination((north, east), 180).latitude
            elif case == Cases.AB:
                south = map_south
                north = FULL_KILOMETER_GEODESIC.destination((south, west), 0).latitude
            elif case == Cases.CD:
                north = map_north
                south = FULL_KILOMETER_GEODESIC.destination((north, west), 180).latitude
            elif case == Cases.AD:
                east = map_east
                west = FULL_KILOMETER_GEODESIC.destination((north, east), -90).longitude
            elif case == Cases.BC:
                west = map_west
                east = FULL_KILOMETER_GEODESIC.destination((north, west), 90).longitude
            else:
                raise RuntimeError('Impossible case %s' % case)
    # Get points in rectangle.
    return get_points_in_rectangle(coordinates, north, south, west, east)


def main():
    if len(sys.argv) != 3:
        print('Usage: python flood.py <map-file-name> <flood-threshold>')
        exit(-1)
    map_file_name = sys.argv[1]
    flood_threshold = float(sys.argv[2])
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
                    flood.append(Point(float(pieces[LAT]), float(pieces[LNG]), alt))
                if (index_line + 1) % debug_step == 0:
                    print('Loaded line', index_line + 1, '/', size)
    assert (index_line + 1) == size == width * height
    print('Finished loading map.')

    print('Got', len(flood), 'flooded points /', size, 'with threshold', flood_threshold,
          '(%s %%)' % (len(flood) * 100 / size))

    lat_to_points = {}  # type: Dict[float, List[Point]]
    map_north = flood[0].lat
    map_south = flood[0].lat
    map_west = flood[0].lng
    map_east = flood[0].lng
    lat_to_points[flood[0].lat] = [flood[0]]
    with Profiler('Find whole flood bounds and range points per latitude.'):
        for i in range(1, len(flood)):
            point = flood[i]
            if map_north < point.lat:
                map_north = point.lat
            if map_south > point.lat:
                map_south = point.lat
            if map_west > point.lng:
                map_west = point.lng
            if map_east < point.lng:
                map_east = point.lng
            lat_to_points.setdefault(point.lat, []).append(point)

    with Profiler('Generate flood coordinates table.'):
        for lat in lat_to_points:
            lat_to_points[lat].sort()
        coordinates = [lat_to_points[lat] for lat in sorted(lat_to_points)]

    # A---B
    # |   |
    # D---C
    simulation = {}
    with Profiler('Find neighbors for each point.'):
        for i_pt, point in enumerate(flood):
            simulation[point] = get_neighbors(point, coordinates, map_north, map_south, map_west, map_east)
            if i_pt % 2000 == 0:
                print(i_pt + 1, '/', len(flood))
    print(min(len(r) for r in simulation.values()), max(len(r) for r in simulation.values()))
    exit(-1)

    sorted_lat_and_points = [(lat, lat_to_points[lat]) for lat in sorted(lat_to_points)]
    nb_latitudes = len(sorted_lat_and_points)
    start = 0
    cursor = 1
    with Profiler('Find groups among %d latitude(s)' % len(sorted_lat_and_points)):
        while start < nb_latitudes:
            prev_lat = sorted_lat_and_points[start][0]
            limit = FULL_KILOMETER_GEODESIC.destination((prev_lat, 0), 0)
            while True:
                if cursor < nb_latitudes:
                    if sorted_lat_and_points[cursor][0] <= limit.latitude:
                        cursor += 1
                    else:
                        break
                else:
                    cursor = nb_latitudes
                    break
            print('Computing [%d; %d]' % (start, cursor - 1))
            local_points = []
            for i in range(start, cursor):
                local_points.extend(sorted_lat_and_points[i][1])
            local_points.sort(key=lambda pt: (pt.lng, pt.lat))
            for j in range(1, len(local_points)):
                prev_point = local_points[j - 1]
                curr_point = local_points[j]
                local_distance = geodesic(prev_point.position, curr_point.position).meters
                if local_distance <= 1000:
                    prev_point.connect(curr_point, local_distance)
            if cursor == start + 1:
                start = cursor
            elif cursor < nb_latitudes:
                distance = geodesic((sorted_lat_and_points[cursor - 1][0], 0),
                                    (sorted_lat_and_points[cursor][0], 0)).meters
                if distance <= 1000:
                    start = cursor - 1
                else:
                    start = cursor
            else:
                break
            cursor = start + 1

    with Profiler('Isolate groups'):
        groups = isolate_groups(flood)

    valid_groups = [group for group in groups if len(group) > 1]
    rectangle_centers = []
    print('Found', len(valid_groups), '/', len(groups), 'valid groups (with at least 2 points).')

    with Profiler('Compute rectangles'):
        for group in valid_groups:
            rectangle_centers.append(select_rectangle_centers(group))

    for i in range(len(valid_groups)):
        print('Group', i + 1, 'with', len(valid_groups[i]), 'points represented with',
              len(rectangle_centers[i]), 'rectangle(s).')
        for rectangle in rectangle_centers[i]:
            print('\t', rectangle)


if __name__ == '__main__':
    main()
