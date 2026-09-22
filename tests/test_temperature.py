from iox_stats.temperature import parse_macmon_line, parse_osx_cpu_temp


def test_parse_macmon_ok():
    assert parse_macmon_line('{"temp":{"cpu_temp_avg":47.3,"gpu_temp_avg":41.0},"memory":{}}') == 47.3


def test_parse_macmon_bad_input():
    assert parse_macmon_line("") is None
    assert parse_macmon_line("not json") is None
    assert parse_macmon_line('{"temp":{}}') is None
    assert parse_macmon_line('{"temp":{"cpu_temp_avg":0}}') is None
    assert parse_macmon_line('{"temp":{"cpu_temp_avg":999}}') is None


def test_parse_osx_cpu_temp():
    assert parse_osx_cpu_temp("61.2°C") == 61.2
    assert parse_osx_cpu_temp("61,2 C\n") == 61.2
    assert parse_osx_cpu_temp("0.0°C") is None
    assert parse_osx_cpu_temp("error") is None
