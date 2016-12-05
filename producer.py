#!/usr/bin/env python3
import begin
from faker import Factory
from urllib.parse import urljoin
import requests
from pprint import pprint
from datetime import timedelta
import time
import os
import sys

fake = Factory.create('en_US')
base_path = "/services-1.0.0"

def make_new_user(server, superuser):
    su_auth_header = authenticate_user(server, superuser)
    user_data = {
            "username" : fake.user_name(),
            "givenname": fake.first_name(),
            "surname"  : "McTestface",
            "password" : "hunter2"
    }
    r = requests.post(server + '/user', json=user_data, headers=su_auth_header)
    if r.status_code is not 200:
        print('\n--{:=^50}--'.format(' New User NOT Created '))
        print(r.json()['message'])
        sys.exit(1)
    print('\n--{:=^50}--'.format(' New User Created '))
    pprint(r.json())
    return r.json()['username'], "hunter2"

def authenticate_user(server, user):
    user_data = {"username": user[0], "password": user[1]}
    r = requests.post(server + '/auth', json=user_data)
    if r.status_code is not 200:
        print('\n--{:=^50}--'.format(' User NOT Authenticated '))
        print(r.json()['message'])
        sys.exit(1)
    print('\n--{:=^50}--'.format(' User Authenticated '))
    pprint(r.json())
    return {"Authorization": "Sleepy token=" + r.json()['token']}

def make_vehicle(server, auth_header):
    car_data = {
            "make" : fake.company(),
            "model" : fake.word().capitalize(),
            "vintage" : fake.year(),
            "vin" : fake.ean13()
    }
    r = requests.post(server + '/vehicle', json=car_data, headers=auth_header)
    if r.status_code is not 200:
        print('\n--{:=^50}--'.format(' Vehicle NOT Created '))
        print(r.json()['message'])
        sys.exit(1)
    print('\n--{:=^50}--'.format(' Vehicle Created '))
    pprint(r.json())
    return str(r.json()['id'])

def make_route(server, auth_header, vehicle_id):
    route_data = { "vehicleid": vehicle_id, "routeState": "CREATED" }
    r = requests.post(server + '/route', json=route_data, headers=auth_header)
    if r.status_code is not 200:
        print('\n--{:=^50}--'.format(' Route NOT Created '))
        print(r.json()['message'])
        sys.exit(1)
    print('\n--{:=^50}--'.format(' Route Created '))
    pprint(r.json())
    return str(r.json()['id'])

def change_route_state(server, auth_header, route_id, state):
    route_data = { "routeState": state }
    r = requests.put(server + '/route/' + route_id, json=route_data, headers=auth_header)
    if r.status_code is not 200:
        print('\n--{:=^50}--'.format(' Route State NOT Changed '))
        print(r.json()['message'])
        sys.exit(1)
    print('\n--{:=^50}--'.format(' Route State Changed '))
    pprint(r.json())

def make_waypoint(server, auth_header, route_id, latitude, longitude):
    waypoint_data = {
            "latitude" : latitude,
            "longitude": longitude,
            "timestamp": int(time.time() * 1000)
    }
    r = requests.post(server + '/route/' + route_id + '/waypoint', json=waypoint_data, headers=auth_header)
    if r.status_code is not 200:
        print('\n--{:=^50}--'.format(' Waypoint NOT Created '))
        print(r.json()['message'])
    else:
        print('\n--{:=^50}--'.format(' Waypoint Created '))
        pprint(r.json())

def get_route_from_google_maps(start, end, force=False):
    import googlemaps
    import polyline
    if not 'GOOGLE_MAPS_API_KEY' in os.environ.keys():
        print("Google Maps API Key must be in environment variables as: GOOGLE_MAPS_API_KEY")
        sys.exit(0)
    api_key = os.environ['GOOGLE_MAPS_API_KEY']
    gmaps = googlemaps.Client(key=api_key)
    try:
        directions = gmaps.directions(start, end, mode="driving", alternatives=True)
    except Exception as e:
        print("ERROR: ", str(e))
        sys.exit(1)
    route = None
    if not force and len(directions) > 1:
        print("Multiple routes found.\nChoose one:")
        for i, route in enumerate(directions):
            distance = sum([leg['distance']['value'] for leg in route['legs']])
            print('  {}. {} ({:.2f} km)'.format(i, route['summary'], distance / 1000))
        while True:
            choice = input('Choose #: ')
            if choice.isdigit() and int(choice) in range(len(directions)):
                route = directions[int(choice)]
                break
    else:
        route = directions[0]
    duration = sum([leg['duration']['value'] for leg in route['legs']])
    coordinates = []
    for leg in route['legs']:
        for step in leg['steps']:
            pline = step['polyline']['points']
            coordinates.extend(polyline.decode(pline))
    return coordinates, duration

def get_route_from_gpx_file(file):
    import gpxpy
    gpx = None
    with open(waypoints, 'r') as f:
        gpx = gpxpy.parse(f)
    coordinates = []
    for segment in gpx.tracks[0].segments:
        for point in segment.points:
            coordinates.append((point.latitude, point.longitude))
    return coordinates, len(coordinates)

@begin.start(auto_convert=True)
def main(server: 'URL of the server' = "http://sw708e16.cs.aau.dk",
         user: 'If not supplied a new user will be made' = (None, None),
         superuser: 'Used to make new user' = ("deadpool", "hunter2"),
         waypoints: 'GPX file to read waypoints from' = None,
         delay: 'Manual delay between POSTing waypoints' = 1.0,
         start: 'coordinates or address of starting point' = None,
         end: 'coordinates or address of ending point' = None,
         non_interactive: 'Disable user input (force choices to first)' = False):
    points = None
    duration = 0
    if start and end:
        points, duration = get_route_from_google_maps(start, end, force=non_interactive)
    elif waypoints:
        points, duration = get_route_from_gpx_file(waypoints)
    else:
        print("You must use either start and end point or gpx file with waypoints.")
        sys.exit(1)
    delay = delay if delay > 0 else duration / len(points)
    server = urljoin(server, base_path)
    print(server)
    if user[0] is None:
        user = make_new_user(server, superuser)
    auth_header = authenticate_user(server, user)
    vehicle_id = make_vehicle(server, auth_header)
    route_id = make_route(server, auth_header, vehicle_id)
    change_route_state(server, auth_header, route_id, "ACTIVE")

    for i, point in enumerate(points):
        t = time.time()
        make_waypoint(server, auth_header, route_id, latitude=point[0], longitude=point[1])
        print('{} out of {} | estimated time left: {}'.format(i+1, len(points), timedelta(seconds= delay * (len(points) - i))))
        if time.time() - t < delay:
            time.sleep(delay - (time.time() - t))

    change_route_state(server, auth_header, route_id, "COMPLETE")
