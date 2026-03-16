from app.services.gateway_service import (
    GatewayConfig,
    build_gateway_client_target,
    normalize_gateway_config,
)


def test_normalize_gateway_config_adds_leading_slash():
    config = normalize_gateway_config({"listen_host": "127.0.0.1", "port": 10570, "path": "telemetry"})

    assert config.path == "/telemetry"


def test_build_gateway_client_target_prefers_advertised_host():
    target = build_gateway_client_target(
        GatewayConfig(
            listen_host="0.0.0.0",
            port=10570,
            path="/telemetry",
            advertised_host="192.168.1.50",
        )
    )

    assert target == {
        "host": "192.168.1.50",
        "port": 10570,
        "path": "/telemetry",
    }
