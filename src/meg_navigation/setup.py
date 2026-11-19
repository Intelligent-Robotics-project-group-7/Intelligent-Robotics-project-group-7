from glob import glob
from setuptools import find_packages, setup


package_name = 'meg_navigation'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Meg',
    maintainer_email='344957791+Meg0902@users.noreply.github.com',
    description='TurtleBot 4 A* navigation and rescue mission',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'rescue_mission = meg_navigation.mission:main',
        ],
    },
)
