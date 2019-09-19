import setuptools

setuptools.setup(
    name='python-ccai',
    version='0.1',
    packages=setuptools.find_packages(),
    install_requires=[
        'ujson',
        'Pillow',
        'geopy',
    ],
    url='',
    license='GPL',
    author='notoraptor',
    author_email='',
    description='Script to generate heightmap of elevations from geographical bounds using '
                'Google Elevation API.'
)
