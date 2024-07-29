"""Device handler for Tuya Zigbee Vibration Door Sensor.

The device reports:
- Vibration
- Open/Closed door/window
- Remaining battery percentage

Extra details: https://www.aliexpress.com/item/1005004443361928.html?spm=a2g0o.order_list.order_list_main.53.35a81802wiZASs
"""

from zigpy.endpoint import Endpoint
from zigpy.profiles import zha
from zigpy.quirks import CustomCluster, CustomDevice
from zigpy.zcl.clusters.general import (
    Basic,
    Groups,
    Ota,
    PowerConfiguration,
    Scenes,
    Time,
)
from zigpy.zcl.clusters.security import IasZone, ZoneStatus, ZoneType

from zhaquirks.const import (
    DEVICE_TYPE,
    ENDPOINTS,
    INPUT_CLUSTERS,
    MODELS_INFO,
    OUTPUT_CLUSTERS,
    PROFILE_ID,
    ZONE_STATE,
)
from zhaquirks.tuya import (
    TUYA_CLUSTER_ID,
    DPToAttributeMapping,
    TuyaLocalCluster,
    TuyaNewManufCluster,
)

DOOR_HANDLE_DP_ID = 1
BATTERY_STATE_DP_ID = 3
VIBRATION_DP_ID = 10

DP_HANDLER_EP_ID = 1
DOOR_HANDLE_EP_ID = 2
VIBRATION_EP_ID = 3


class CustomBasicCluster(CustomCluster, Basic):
    """Custom Basic cluster to report power source."""

    def __init__(self, endpoint: Endpoint, is_server: bool = True):
        """Init constructor that sets the power source to battery."""
        super().__init__(endpoint=endpoint, is_server=is_server)

        self.update_attribute(
            attrid=Basic.AttributeDefs.power_source.id,
            value=Basic.PowerSource.Battery,
        )


class CustomTuyaPowerConfigurationCluster(TuyaLocalCluster, PowerConfiguration):
    """Custom Power Configuration cluster that represents battery reports."""

    def __init__(self, endpoint: Endpoint, is_server: bool = True):
        """Init constructor that initializes battery attributes."""
        super().__init__(endpoint=endpoint, is_server=is_server)

        self.update_attribute(
            attr_name=PowerConfiguration.AttributeDefs.battery_size.name,
            value=PowerConfiguration.BatterySize.AAA,
        )

        self.update_attribute(
            attr_name=PowerConfiguration.AttributeDefs.battery_quantity.name,
            value=2,
        )

        self.update_attribute(
            attr_name=PowerConfiguration.AttributeDefs.battery_percentage_remaining.name,
            value=100 * 2,
            # Device measures battery in 1% steps, while the ZCL specifies it in 0.5% steps
        )


class CustomTuyaContactSwitchCluster(TuyaLocalCluster, IasZone):
    """Custom IasZone cluster that represents the Open/Closed sensor."""

    def __init__(self, endpoint: Endpoint, is_server: bool = True):
        """Init constructor that initializes the major IasZone attributes."""
        super().__init__(endpoint=endpoint, is_server=is_server)

        self.update_attribute(
            attr_name=IasZone.AttributeDefs.zone_state.name,
            value=ZONE_STATE,
        )

        self.update_attribute(
            attr_name=IasZone.AttributeDefs.zone_type.name,
            value=ZoneType.Contact_Switch,
        )

        self.update_attribute(
            attr_name=IasZone.AttributeDefs.zone_status.name,
            value=0x0000,
        )


class CustomTuyaVibrationCluster(TuyaLocalCluster, IasZone):
    """Custom IasZone cluster that represents the vibration sensor."""

    def __init__(self, endpoint: Endpoint, is_server: bool = True):
        """Init constructor that initializes the major IasZone attributes."""
        super().__init__(endpoint=endpoint, is_server=is_server)

        self.update_attribute(
            attr_name=IasZone.AttributeDefs.zone_state.name,
            value=ZONE_STATE,
        )

        self.update_attribute(
            attr_name=IasZone.AttributeDefs.zone_type.name,
            value=ZoneType.Vibration_Movement_Sensor,
        )

        self.update_attribute(
            attr_name=IasZone.AttributeDefs.zone_status.name,
            value=0x0000,
        )


class CustomTuyaDPProcessor(TuyaNewManufCluster):
    """Custom cluster that translates Tuya's data point reporting.

    Tuya data points are parsed and their values are used to update the
    specified endpoint's (endpoint_id) cluster's (ep_attribute)
    attribute (attribute_name).
    """

    dp_to_attribute: dict[int, DPToAttributeMapping] = {
        DOOR_HANDLE_DP_ID: DPToAttributeMapping(
            endpoint_id=DOOR_HANDLE_EP_ID,
            ep_attribute=IasZone.ep_attribute,
            attribute_name=IasZone.AttributeDefs.zone_status.name,
            converter=lambda x: ZoneStatus.Alarm_1 & x,
        ),
        VIBRATION_DP_ID: DPToAttributeMapping(
            endpoint_id=VIBRATION_EP_ID,
            ep_attribute=IasZone.ep_attribute,
            attribute_name=IasZone.AttributeDefs.zone_status.name,
            converter=lambda x: ZoneStatus.Alarm_1 & x,
        ),
        BATTERY_STATE_DP_ID: DPToAttributeMapping(
            endpoint_id=DP_HANDLER_EP_ID,
            ep_attribute=PowerConfiguration.ep_attribute,
            attribute_name=PowerConfiguration.AttributeDefs.battery_percentage_remaining.name,
            converter=lambda x: 2 * x,
            # Device measures battery in 1% steps, while the ZCL specifies it in 0.5% steps
        ),
    }

    data_point_handlers = {
        DOOR_HANDLE_DP_ID: "_dp_2_attr_update",
        VIBRATION_DP_ID: "_dp_2_attr_update",
        BATTERY_STATE_DP_ID: "_dp_2_attr_update",
    }


class TS0601Door(CustomDevice):
    """Quirk for Tuya Zigbee Vibration Door Sensor.

    The device reports:
    - Vibration
    - Open/closed door/window
    - Remaining battery percentage

    The original device has a single endpoint that corresponds to the Tuya
    manufacturer specific cluster. The replacement has 3 endpoints, where
        - the first is responsible for handling the Tuya data point reports,
        - the second represents the open/closed sensor,
        - and the third represents the vibration sensor.
    The latter two are both IasZone cluster extensions, that's why they had to
    be put into different endpoints (otherwise we would have two of the same
    cluster for an endpoint, which is prohibited by the Zigbee standard).

    Extra details about the physical device: https://www.aliexpress.com/item/1005004443361928.html?spm=a2g0o.order_list.order_list_main.53.35a81802wiZASs
    """

    def __init__(self, *args, **kwargs):
        """Init constructor."""
        super().__init__(*args, **kwargs)

    signature = {
        # <SimpleDescriptor endpoint=1 profile=260 device_type=81
        # device_version=1
        # input_clusters=[4, 5, 61184, 0]
        # output_clusters=[25, 10]>
        MODELS_INFO: [("_TZE200_kzm5w4iz", "TS0601")],
        ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.SMART_PLUG,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    TUYA_CLUSTER_ID,
                ],
                OUTPUT_CLUSTERS: [Time.cluster_id, Ota.cluster_id],
            },
        },
    }

    replacement = {
        ENDPOINTS: {
            DP_HANDLER_EP_ID: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.SMART_PLUG,
                INPUT_CLUSTERS: [
                    CustomBasicCluster,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    CustomTuyaPowerConfigurationCluster,
                    CustomTuyaDPProcessor,
                ],
                OUTPUT_CLUSTERS: [Time.cluster_id, Ota.cluster_id],
            },
            DOOR_HANDLE_EP_ID: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.IAS_ZONE,
                INPUT_CLUSTERS: [
                    CustomBasicCluster,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    CustomTuyaContactSwitchCluster,
                ],
                OUTPUT_CLUSTERS: [Time.cluster_id],
            },
            VIBRATION_EP_ID: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.IAS_ZONE,
                INPUT_CLUSTERS: [
                    CustomBasicCluster,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    CustomTuyaVibrationCluster,
                ],
                OUTPUT_CLUSTERS: [Time.cluster_id],
            },
        },
    }