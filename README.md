# Nostalgia Pi

Nostalgia Pi aims to replicate cable TV of old, on a Raspberry Pi. It relies on nothing external, can be completely offline and is totally self sufficient.

The scheduling is controlled via a config file, it allows you to define schedules in the following formats, time, date, day of the week and month.

So for example you could have it play saturday morning cartoons between 6am and 10am, it could play spooky movies all throughout October or valentines movies on the 14th feb, the only limit is your imagination!

The pi can be scheduled to restart the script daily or it can shut the pi down at the end of the day, the choice is yours.

Suggested / tested hardware is a Raspberry Pi 3B + with Raspbian OS installed

If you test on anything else and it works please let me know and i will add this to the supported list.

# Pre-Requisites
There will be some pre-reqs, e.g. packages to install i'm sure, what they are at the minute is not documented, once i get chance to build a pi from
scratch i will update this readme with them

## Config file example

There are 2 config files that can be created:
* config-nt.json - For use on Microsoft Windows
* config-pi.json - For use on Raspberry pi

This can run on Windows but it hasnt been tested outside of the basic logic, this is designed primarily to run on a pi due to its low power requirements.

both config files are the same, the only real difference is the paths for windows and linux are different.. i realise i could solve this with code, maybe i will in future.

** HUGE config-xx.json example **
```
{
  "schedules": {
    "morning": {
	    "comment": "Saturday morning cartoons",
      "priority": 9,
      "daysofweek": [0],
      "dates": [0],
      "months": [0],
      "starthour": 6,
	    "startminute": 0,
      "endhour": 12,
	    "endminute": 0,
      "shows": ["c:\\Videos\\morningshows"],
      "ads": ["c:\\Videos\\morningads"],
	    "bumpers": ["c:\\Videos\\bumpers"],
	    "bumper_chance": 0.9
    },
    "afternoon": {
	    "comment": "afternoon shows",
      "priority": 8,
      "daysofweek": [0],
      "dates": [0],
      "months": [0],
      "starthour": 12,
	    "startminute": 0,
      "endhour": 15,
	    "endminute": 0,
      "shows": ["c:\\Videos\\afternoonshows"],
      "ads": ["c:\\Videos\\afternoonads"],
	    "bumpers": ["c:\\Videos\\bumpers"],
	    "bumper_chance": 0.9
    },
    "teatime": {
	    "comment": "teatime, cartoons and shows",
      "priority": 7,
      "daysofweek": [0],
      "dates": [0],
      "months": [0],
      "starthour": 15,
	    "startminute": 0,
      "endhour": 19,
	    "endminute": 0,
      "shows": ["c:\\Videos\\eveningshows"],
      "ads": ["c:\\Videos\\eveningads"],
	  "bumpers": ["c:\\Videos\\bumpers"],
	  "bumper_chance": 0.7
    },
    "lateevening": {
	    "comment": "usually movies but can be other shows too",
      "priority": 6,
      "daysofweek": [0],
      "dates": [0],
      "months": [0],
      "starthour": 19,
	    "startminute": 0,
      "endhour": 2,
	    "endminute": 0,
      "shows": ["c:\\Videos\\lateeveningshows"],
      "ads": ["c:\\Videos\\lateeveningads"],
	    "bumpers": ["c:\\Videos\\bumpers"],
	    "bumper_chance": 0.1
    },
    "night": {
	    "comment": "dead of the night, who knows what is here? twlight zone episodes?",
      "priority": 5,
      "daysofweek": [0],
      "dates": [0],
      "months": [0],
      "starthour": 2,
	    "startminute": 0,
      "endhour": 6,
	    "endminute": 0,
      "shows": ["c:\\Videos\\nightshows"],
      "ads": ["c:\\Videos\\nightads"],
	    "bumpers": ["c:\\Videos\\bumpers"],
	    "bumper_chance": 0.7
    },
    "halloween": {
	  "comment": "spooky season, lots of horror themed shows & movies",
      "priority": 4,
      "daysofweek": [0],
      "dates": [0],
      "months": [10],
      "starthour": 12,
	    "startminute": 0,
      "endhour": 6,
	    "endminute": 0,
      "shows": ["c:\\Videos\\halloweenshows"],
      "ads": ["c:\\Videos\\halloweenads"],
	    "bumpers": ["c:\\Videos\\bumpers"],
	    "bumper_chance": 0.7
    },
    "xmas": {
	    "comment": "Christmas!! loads of christmas movies",
      "priority": 3,
      "daysofweek": [0],
      "dates": [0],
      "months": [12],
      "starthour": 12,
	    "startminute": 0,
      "endhour": 6,
	    "endminute": 0,
      "shows": ["c:\\Videos\\xmasshows"],
      "ads": ["c:\\Videos\\xmasads"],
	    "bumpers": ["c:\\Videos\\bumpers"],
	    "bumper_chance": 0.7
    },
    "valentines": {
	    "comment": "valentines day, plenty of rom coms",
      "priority": 2,
      "daysofweek": [0],
      "dates": [14],
      "months": [2],
      "starthour": 12,
	    "startminute": 0,
      "endhour": 6,
	    "endminute": 0,
      "shows": ["c:\\Videos\\valentinesshows"],
      "ads": ["c:\\Videos\\valentinesads"],
	    "bumpers": ["c:\\Videos\\bumpers"],
	    "bumper_chance": 0.7
    },
    "newyears": {
	    "comment": "new years day",
      "priority": 1,
      "daysofweek": [0],
      "dates": [1],
      "months": [1],
      "starthour": 12,
	    "startminute": 0,
      "endhour": 6,
	    "endminute": 0,
      "shows": ["c:\\Videos\\newyearsshows"],
      "ads": ["c:\\Videos\\newyearsads"],
	    "bumpers": ["c:\\Videos\\bumpers"],
	    "bumper_chance": 0.7
    },
    "classicscifimonth": {
	    "comment": "August is 50s/60s classic Sci-Fi month",
      "priority": 1,
      "daysofweek": [0],
      "dates": [0],
      "months": [8],
      "starthour": 12,
	    "startminute": 0,
      "endhour": 6,
	    "endminute": 0,
      "shows": ["c:\\Videos\\classicscifi"],
      "ads": ["c:\\Videos\\ads-50s60s"],
	    "bumpers": ["c:\\Videos\\bumpers"],
	    "bumper_chance": 0.7
    }
  },
  "system": {
    "action": "restart",
    "hour": 3,
    "minute": 0,
	"create_debug_file": false,
    "webuiport": 8080,
	"channel_name": "90s overload",
	"peers": [
      {
        "name": "Living Room",
        "url": "http://192.168.1.1:8080/queued"
      },
	  {
        "name": "Kitchen",
        "url": "http://192.168.1.2:8080/queued"
      },
	  {
		"name": "Bedroom",
        "url": "http://192.168.1.3:8080/queued"
      }
    ]
  }
}
```
The "action" property under system can be restart (which restarts the script) or shutdown, which shuts the pi down

Multiple Pis can be used together to create multiple channels, the schedule viewer on the web interface will dynamically display any number of channels
Each channel can have a unique name, it is recommended to have 1 "master" pi that has the peers listed, the other pis should just supply a channel_name value

The above json file will be included in the repo to use as a template.

NOTE: 
* When schedules overlap the highest priority will win
* When 2 schedules overlap AND share the same priority the highest in the json will win
* Recommended to make day-to-day schedules a very low priority e.g. Morning, Afternoon & Evening Priority 100, 101 and 102 respectively
* Recommended to then make month/Date or Day of the week specific items a higher priority then these will win when expected and fallback to the morn/aft/evening almost as defaults

** Duration Analysis **
Media is analysed on startup and durations are written to "durations.json", this is used for lookups and building the playlist, 
if any media is unreadable then a "duration_errors.json" file will be generated that contains the files with issues, 
it is recommended to remove/replace any files this identifies. 

** Debugging **

There is currently no debugging built in, this will be added in future via a flag in the config file

Any support would be greatly appreciated, my Kofi link is included, thank you

Please raise any issues you find for fixing, thank you!
