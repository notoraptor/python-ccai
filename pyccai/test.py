from geopy.distance import geodesic


def print_point(el):
    print(el.latitude, el.longitude)

def main():
    lat = 0
    lng = 0
    distance = 5000
    calculator = geodesic(meters=distance)
    print(lat, lng)
    print_point(calculator.destination((lat, lng), 0))
    print_point(calculator.destination((lat, lng), 90))
    print_point(calculator.destination((lat, lng), 180))
    print_point(calculator.destination((lat, lng), 270))
    print_point(calculator.destination((lat, lng), 360))

if __name__ == '__main__':
    main()
