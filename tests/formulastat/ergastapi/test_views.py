import json
from pathlib import Path

import pytest
from rest_framework.test import APIClient


def get_acceptable_time_range(time_str: str) -> tuple[str, str]:
    if ":" in time_str:
        time, time_decimal = time_str.rsplit(":", maxsplit=1)
        time += ":"
        if float(time_decimal) < 10:
            time += "0"
    else:
        time = "+"
        time_decimal = time_str[1:]
    time_decimal = float(time_decimal)

    time_range = (
        time_str.rstrip("0"),
        f"{time}{round((time_decimal) + 0.001,3)}",
    )
    return time_range


@pytest.mark.parametrize(
    ["endpoint", "endpoint_fixture"],
    list((path.name.replace("@", "/"), path) for path in Path("tests/fixtures/ergast_responses").glob("**/*.json*")),
)
@pytest.mark.django_db
def test_viewsets(client: APIClient, endpoint_fixture: Path, endpoint, django_assert_max_num_queries):
    # endpoint = endpoint_fixture.name.replace("@", "/")
    with open(endpoint_fixture, mode="rb") as f:
        expected = json.load(f)

    # We intentially do not match the xmlns or url
    expected["MRData"]["xmlns"] = ""
    expected["MRData"]["url"] = expected["MRData"]["url"].replace(
        "http://ergast.com/api/f1/",
        "http://testserver/ergast/",
    )

    with django_assert_max_num_queries(8) as captured:
        response = client.get(f"/ergast/{endpoint}")
    assert response.status_code == 200

    result = response.json()

    # Special case for results data, allow text time to be off by 1 millisecond
    # This is because in ergast the millis time and text based time is inconsistent
    if "results.json" in endpoint or "sprint.json" in endpoint:
        if "sprint.json" in endpoint:
            result_prefix = "Sprint"
        else:
            result_prefix = ""
        for i, race_data in enumerate(result["MRData"]["RaceTable"]["Races"]):
            for j, result_data in enumerate(race_data[f"{result_prefix}Results"]):
                expected_data = expected["MRData"]["RaceTable"]["Races"][i][f"{result_prefix}Results"][j]
                if expected_data.get("positionText") == "N":
                    expected_data["positionText"] = "R"
                if result_data.get("Time"):
                    time_range = get_acceptable_time_range(result_data["Time"]["time"])
                    # rstrip as ergast is inconsistent with trailing 0s
                    assert expected_data["Time"]["time"].rstrip("0") in time_range
                    del result_data["Time"]["time"]
                    del expected_data["Time"]["time"]
    if "laps.json" in endpoint:
        for i, race_data in enumerate(result["MRData"]["RaceTable"]["Races"]):
            for j, laps_data in enumerate(race_data["Laps"]):
                for k, timing_data in enumerate(laps_data["Timings"]):
                    expected_data = expected["MRData"]["RaceTable"]["Races"][i]["Laps"][j]["Timings"][k]
                    if timing_data.get("time"):
                        time_range = get_acceptable_time_range(timing_data["time"])
                        # rstrip as ergast is inconsistent with trailing 0s
                        assert expected_data["time"].rstrip("0") in time_range
                        del timing_data["time"]
                        del expected_data["time"]

    assert result == expected