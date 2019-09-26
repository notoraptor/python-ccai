import sys
from pyccai.heightmap import Profile
import ujson as json
import urllib.parse

def main():
    if len(sys.argv) != 3:
        return
    json_path = sys.argv[1]
    output_path = sys.argv[2]
    print('Opening JSON ...')
    with open(json_path) as file:
        data = json.load(file)
    points = []
    total_samples = 0
    count = 0
    print('Reading JSON ...')
    for url, values in data.items():
        parameters = urllib.parse.parse_qs(url.split('?', 1)[1])
        n_samples = int(parameters['samples'][0])
        assert len(values) == n_samples > 1
        total_samples += n_samples
        string_from, string_to = parameters['path'][0].split('|')
        string_from_lat, string_from_lng = string_from.split(',')
        string_to_lat, string_to_lng = string_to.split(',')
        from_lat = float(string_from_lat)
        from_lng = float(string_from_lng)
        to_lat = float(string_to_lat)
        to_lng = float(string_to_lng)
        assert from_lat == to_lat
        lng_gap = to_lng - from_lng
        estimated_lng_step = lng_gap / (n_samples - 1)
        latest_point = (from_lat, from_lng, values[0][0], values[0][1], estimated_lng_step)
        points.append(latest_point)
        for i in range(n_samples - 2):
            latest_point = (from_lat, latest_point[1] + estimated_lng_step, values[i + 1][0], values[i + 1][1], estimated_lng_step)
            points.append(latest_point)
        points.append((to_lat, to_lng, values[-1][0], values[-1][1], estimated_lng_step))
        count += 1
        if count % 2000 == 0:
            print('Reading entry', count + 1, '/', len(data))
    print('Finished reading.')
    assert total_samples == len(points)
    step_to_points = {}
    for point in points:
        step = point[-1]
        step_to_use = None
        for saved_step in step_to_points:
            if abs(saved_step - step) < 1e-10:
                step_to_use = saved_step
                break
        if step_to_use is None:
            step_to_use = step
        step_to_points.setdefault(step_to_use, []).append(point)
    max_step, max_points = None, []
    for step, step_points in step_to_points.items():
        if len(max_points) < len(step_points):
            max_step, max_points = step, step_points
    print('Extracted', len(max_points), 'points')
    lat_to_nb_points = {}
    line_length = 0
    for point in max_points:
        line_length = max(line_length, len(' '.join(str(value) for value in point[:-1])))
        lat = point[0]
        if lat in lat_to_nb_points:
            lat_to_nb_points[lat] += 1
        else:
            lat_to_nb_points[lat] = 1
    assert len(set(lat_to_nb_points.values())) == 1
    height = len(lat_to_nb_points)
    width = next(iter(lat_to_nb_points.values()))
    print('Size:', width, 'x', height, '=', len(max_points))
    print('line length', line_length)
    print('Sorting')
    max_points.sort(key=lambda val: (val[0], val[1]))
    print('Sorted, writing into', output_path)
    with open(output_path, 'w') as file:
        file.write(('# %s %s %s lat lng alt res' % (width, height, len(max_points))).ljust(line_length))
        file.write('\n')
        for point in max_points:
            file.write((' '.join(str(value) for value in point[:-1])).ljust(line_length))
            file.write('\n')
    print('End')

if __name__ == '__main__':
    main()
