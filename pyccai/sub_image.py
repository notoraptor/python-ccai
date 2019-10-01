import sys

from PIL import Image


def main():
    if len(sys.argv) != 3:
        return
    image_file_name = sys.argv[1]
    output_file_name = sys.argv[2]
    image = Image.open(image_file_name)
    if image.mode != 'RGB':
        image = image.convert('RGB')
    width, height = image.size
    red_pixels = []
    for index_pixel, pixel in enumerate(image.getdata()):
        if pixel == (255, 0, 0):
            y = index_pixel // width
            x = index_pixel % width
            red_pixels.append((x, y))
    assert len(red_pixels) == 2
    (x_1, y_1), (x_2, y_2) = red_pixels
    new_width = (x_2 - x_1 + 1)
    new_height = (y_2 - y_1 + 1)
    left = x_1
    upper = y_1
    right = x_2 + 1
    lower = y_2 + 1
    crop = image.crop((left, upper, right, lower))
    print(width, height)
    print(new_width, new_height)
    print(crop.size)
    crop.save(output_file_name)


if __name__ == '__main__':
    main()
