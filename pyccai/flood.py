import sys
from typing import Dict, List, Iterable, Set

from geopy.distance import geodesic

from pyccai.profiling import Profiler

LAT, LNG, ALT, RES = 0, 1, 2, 3

KILOMETER = 1000
DEMI_KILOMETER_GEODESIC = geodesic(meters=KILOMETER / 2)
FULL_KILOMETER_GEODESIC = geodesic(meters=KILOMETER)


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


def are_neighbors(rectangle_center, point):
    # type: (Point, Point) -> bool
    # rectangle is approximated to a circle. Not very accurate ...
    return geodesic(rectangle_center.position, point.position).meters <= 1000


def in_rectangle(point, north, south, west, east):
    # type: (Point, float, float, float, float) -> bool
    # lat increases from bottom to top
    # lng increases from left to right
    return south <= point.lat <= north and west <= point.lng <= east


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
            if in_rectangle(neighbor, north, south, west, east):
                group.append(neighbor)
            else:
                new_points.append(neighbor)
        bounds = Bounds(group)
        points = new_points
        centers.append(bounds)
        if points:
            print('\tremaining', len(points))
    return centers


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
    for point in flood:
        lat_to_points.setdefault(point.lat, []).append(point)
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
