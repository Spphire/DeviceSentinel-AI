from app.data.simulator import SimulationEngine, build_device_config


def test_stable_template_stays_within_normal_thresholds():
    engine = SimulationEngine(
        configs=[build_device_config("SGCC-LV-001", "stable", device_index=0)],
        seed=7,
    )

    for _ in range(200):
        engine.step()
        snapshot = engine.get_device_snapshot("SGCC-LV-001")
        analysis = snapshot["analysis"]
        point = snapshot["point"]

        assert point is not None
        assert point.device_status == "online"
        assert analysis["status"] == "normal"
        assert analysis["issues"] == []


def test_frequent_fault_template_has_more_anomalies_than_intermittent_fault():
    intermittent_engine = SimulationEngine(
        configs=[build_device_config("SGCC-LV-001", "intermittent_fault", device_index=0)],
        seed=21,
    )
    frequent_engine = SimulationEngine(
        configs=[build_device_config("SGCC-LV-001", "frequent_fault", device_index=0)],
        seed=21,
    )

    intermittent_anomalies = 0
    frequent_anomalies = 0

    for _ in range(200):
        intermittent_engine.step()
        frequent_engine.step()

        if intermittent_engine.get_device_snapshot("SGCC-LV-001")["analysis"]["status"] != "normal":
            intermittent_anomalies += 1
        if frequent_engine.get_device_snapshot("SGCC-LV-001")["analysis"]["status"] != "normal":
            frequent_anomalies += 1

    assert frequent_anomalies > intermittent_anomalies


def test_offline_template_generates_offline_points_with_missing_values():
    engine = SimulationEngine(
        configs=[build_device_config("SGCC-LV-001", "offline", device_index=0)],
        seed=3,
    )

    offline_points = []
    for _ in range(120):
        engine.step()
        snapshot = engine.get_device_snapshot("SGCC-LV-001")
        point = snapshot["point"]
        if point is not None and point.device_status == "offline":
            offline_points.append(point)

    assert offline_points
    assert all(point.temperature is None for point in offline_points)
    assert all(point.voltage is None for point in offline_points)
    assert all(point.current is None for point in offline_points)


def test_offline_template_generates_offline_analysis_without_threshold_alarm():
    engine = SimulationEngine(
        configs=[build_device_config("SGCC-LV-001", "offline", device_index=0)],
        seed=3,
    )

    offline_analysis = None
    for _ in range(120):
        engine.step()
        snapshot = engine.get_device_snapshot("SGCC-LV-001")
        analysis = snapshot["analysis"]
        if analysis["status"] == "offline":
            offline_analysis = analysis
            break

    assert offline_analysis is not None
    assert offline_analysis["device_status"] == "offline"
    assert offline_analysis["issues"][0]["category"] == "connectivity"
