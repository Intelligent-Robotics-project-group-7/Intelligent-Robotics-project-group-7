from setuptools import find_packages, setup

package_name = 'localisation_mapping'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch',
            ['launch/slam_mapping.launch.py']),
        ('share/' + package_name + '/config',
            ['config/slam_params.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='sreya',
    maintainer_email='sxv358@student.bham.ac.uk',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
    'console_scripts': [
        'occupancy_grid_mapper = localisation_mapping.occupancy_grid_mapper:main',
    ],
},
)
