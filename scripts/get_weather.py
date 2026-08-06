import json
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


OUT_DIR = Path("output/weather")
OUT_FILE = OUT_DIR / "latest.json"


REGIONS = {

    "north": {
        "name": "华北东北",
        "city": "Beijing",
        "lat": 39.9042,
        "lon": 116.4074,
    },

    "east": {
        "name": "华中华东",
        "city": "Shanghai",
        "lat": 31.2304,
        "lon": 121.4737,
    },

    "south": {
        "name": "华南",
        "city": "Guangzhou",
        "lat": 23.1291,
        "lon": 113.2644,
    },

    "southwest": {
        "name": "西南",
        "city": "Chengdu",
        "lat": 30.5728,
        "lon": 104.0668,
    },

    "northwest": {
        "name": "西北",
        "city": "Xi'an",
        "lat": 34.3416,
        "lon": 108.9398,
    },

}



WEATHER_CODE_MAP = {

    0:"晴",
    1:"晴到多云",
    2:"多云",
    3:"阴",

    45:"雾",
    48:"雾",

    51:"小雨",
    53:"小雨",
    55:"中雨",

    61:"小雨",
    63:"中雨",
    65:"大雨",

    71:"小雪",
    73:"中雪",
    75:"大雪",

    80:"阵雨",
    81:"阵雨",
    82:"强阵雨",

    95:"雷阵雨",
    96:"雷阵雨",
    99:"强雷阵雨"

}



def fetch_weather(lat,lon):


    params={

        "latitude":lat,

        "longitude":lon,

        "daily":
        ",".join([

            "weather_code",

            "temperature_2m_max",

            "temperature_2m_min",

        ]),


        "forecast_days":3,

        "timezone":"Asia/Shanghai"

    }



    url = (

        "https://api.open-meteo.com/v1/forecast?"

        + urllib.parse.urlencode(params)

    )


    req=urllib.request.Request(

        url,

        headers={

            "User-Agent":"Mozilla/5.0"

        }

    )


    with urllib.request.urlopen(
        req,
        timeout=40
    ) as resp:


        return json.loads(
            resp.read().decode("utf-8")
        )





def weather_text(code):

    return WEATHER_CODE_MAP.get(
        int(code),
        "多云"
    )





def weather_alert(code,temp):

    """
    只判断异常天气
    """

    code=int(code)


    if code in [
        95,
        96,
        99
    ]:

        return "雷雨"

    
    if code in [
        80,
        81,
        82
    ]:

        return "阵雨"


    if temp>=38:

        return "高温"


    return ""






def main():


    result={


        "generated_at":
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),


        "source":
        "Open-Meteo",


        "regions":{}

    }




    for key,cfg in REGIONS.items():


        raw=fetch_weather(

            cfg["lat"],

            cfg["lon"]

        )


        daily=raw.get(
            "daily",
            {}
        )



        days=[]


        for i in range(3):


            max_temp=round(
                float(
                    daily["temperature_2m_max"][i]
                ),
                1
            )


            min_temp=round(
                float(
                    daily["temperature_2m_min"][i]
                ),
                1
            )


            code=int(
                daily["weather_code"][i]
            )


            days.append({

                "date":
                daily["time"][i],


                "weather":
                weather_text(code),


                "temp_max":
                max_temp,


                "temp_min":
                min_temp,


                "alert":
                weather_alert(
                    code,
                    max_temp
                )

            })



        result["regions"][key]={


            "name":
            cfg["name"],


            "city":
            cfg["city"],


            "days":
            days

        }



    OUT_DIR.mkdir(

        parents=True,

        exist_ok=True

    )


    OUT_FILE.write_text(

        json.dumps(

            result,

            ensure_ascii=False,

            indent=2

        ),

        encoding="utf-8"

    )



    print(
        f"Saved weather data to {OUT_FILE}"
    )





if __name__=="__main__":

    main()
