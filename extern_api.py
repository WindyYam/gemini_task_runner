# This file contains python APIs to be used in code snippet for execution
# To execute the code, put the code in python code snippet in the response

import requests
from bs4 import BeautifulSoup
import json
import serial
from datetime import datetime

house = {
    'light_state' : False,
    'door_state' : False,
    'air_conditioner_set_temp' : 30,
    'fan_speed' : 0,
    }

try:
    ser = serial.Serial(
        port='COM6',  # Change this to the appropriate port name
        baudrate=115200,  # Set the baud rate
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=1  # Set a read timeout value, None for no timeout
    )
except Exception as e:
    print(e)

##########################################################
# APIs for controlling
##########################################################
# control light on and off
def light(on:bool):
    house['light_state'] = on
    print(f'light is {on}')

# control door open and close
def door(open:bool):
    house['door_state'] = open
    print(f'door is {open}')

# control the air conditioner in celsius degree
def setAirConditioner(temp:float):
    house['air_conditioner_set_temp'] = temp
    print(f'set air conditioner to {temp}')

# set fan speed, range from 0 to 100
def setFanSpeed(speed:int):
    house['fan_speed'] = speed
    data = f'{speed} '
    ser.write(data.encode())

##########################################################
# APIs for getting information that you don't know
# At the end, to get the information, you should use attach_to_context(value) on the returned value, I'll then send the value to you
##########################################################
# check for all house smart appliance status
def getHouseStatus()->str:
    return json.dumps(house)

# get the current city name
def getCity()->str:
    res = requests.get('https://ipinfo.io/')
    data = res.json()
    citydata = data['city']
    return(citydata)

# get weather and temperature info
def getWeatherInfo(city_name:str)->str:
    url = 'https://wttr.in/{}'.format(city_name)
    res = requests.get(url)
    return res.text

# online search for any information you don't know from bing search engine 
def bingSearch(query:str)->str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
    }
    url = f'https://bing.com/search?q={query.replace(" ","+")}&count=5'

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    search_results = []

    for result in soup.find_all('li', class_='b_algo'):
        anchor = result.find('a')
        title = anchor.text
        #url = result.find('a')['href']
        desc = result.find('p') or anchor
        description= desc.text
        
        search_results.append({
            'description': description
        })
    
    return json.dumps(search_results)

##########################################################
# apart from the above APIs, you also get access to the following python library/API:
# datetime                          for datetime.
# time                              for time.
# request                           for http request.
# attach_to_context(value)          force me to attach the value information to you at next request.
# photo_stream_mode(on)             for turning on/off continuous photo capture & upload mode on every talk to you, arg is True/False. When it is set on, be aware that you don't need attach_to_context() for the photo
# capture_photo()                   for capturing the photo through your eye. this return the photo instance. when I instruct you to look, you can look and see, by taking a photo. To get that photo file, put attach_to_context(capture()) in the code snippet to instruct me to upload that photo to you.
# switch_user_voice()               for voice system switching to user voice to mimic the user's voice tone only, and your personality keeps unchanged.
# switch_trump_role()               for voice system switching to Donald Trump's voice tone. After this call, you would be Donald Trump as well.
# switch_biden_role()               for voice system switching to Joe Biden's voice tone. After this call, you would be Joe Biden as well.
# switch_robot_role()               for voice system switching to a robot's voice tone. After this call, you would behave like a robot, but without pause and noise sound in response.
# switch_vader_role()               for voice system switching to Darth Vader's voice tone. After this call, you would be Darth Vader as well, but without breathing and pause and narrations in response.
# revert_default_role()             for voice system reverting back to default voice and role.
# schedule(delay, callback, arg=()) for scheduling a function callback, delay is the delay time from now, arg is the argument for the callback
# play_alarm_sound()                for playing an alarm sound

# important! To get the information returned by python APIs, use attach_to_context() instead of print(), which forces me to run the code then relay the information to you.