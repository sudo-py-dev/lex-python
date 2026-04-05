import re


def parse_time(time_str: str) -> float:
    if time_str.isdigit():
        return float(time_str)

    pattern = r"((?P<w>\d+)w)?((?P<d>\d+)d)?((?P<h>\d+)h)?((?P<m>\d+)m)?((?P<s>\d+)s)?"
    match = re.fullmatch(pattern, time_str)
    if not match:
        return 0.0

    seconds = 0.0
    group_dict = match.groupdict()

    if group_dict["w"]:
        seconds += int(group_dict["w"]) * 604800
    if group_dict["d"]:
        seconds += int(group_dict["d"]) * 86400
    if group_dict["h"]:
        seconds += int(group_dict["h"]) * 3600
    if group_dict["m"]:
        seconds += int(group_dict["m"]) * 60
    if group_dict["s"]:
        seconds += int(group_dict["s"])

    return seconds
