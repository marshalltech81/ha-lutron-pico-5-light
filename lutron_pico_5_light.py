import time
import math

logger.set_level(**{"custom_components.pyscript.apps.lutron_pico_5_light.get_desired_light_brightness_pct": "debug"})

log.debug(f"configuration {pyscript.app_config}")
# logbook.log(name="Hello World", message="Hello from pyscript")

APP_DOMAIN = 'lutron_pico_5_light'

PICO_DEFAULT_BRIGHTNESS_PCT = 25
PICO_DEFAULT_SCENE_NUMBER = -1
PICO_DEFAULT_SCENES = [
    {
        'kelvin': 3500,
        'brightness_pct': 100
    },
    {
        'kelvin': 2500, 
        'brightness_pct': 100
    },
    {
        'rgb_color': [255, 0, 0],
        'brightness_pct': 100
    },
    {
        'rgb_color': [0, 255, 0],
        'brightness_pct': 100
    },
    {
        'rgb_color': [0, 0, 255],
        'brightness_pct': 100
    },
]

PICO_ACTION_ON = 'on'
PICO_ACTION_RAISE = 'raise'
PICO_ACTION_STOP = 'stop'
PICO_ACTION_LOWER = 'lower'
PICO_ACTION_OFF = 'off'

DIM_UP = 1
DIM_DOWN = -1

LIGHT_BRIGHTNESS_MAX = 255
LIGHT_BRIGHTNESS_PCT_MIN = 0
LIGHT_BRIGHTNESS_PCT_MAX = 100

def get_light_brightness_pct(light_entity_id):
    light_entity_state = state.get(light_entity_id)
    light_brightness_pct = 0

    if light_entity_state == "on":
        # brightness only defined when light is on
        light_brightness = state.get(f"{light_entity_id}.brightness")
        light_brightness_pct = round(light_brightness / LIGHT_BRIGHTNESS_MAX * LIGHT_BRIGHTNESS_PCT_MAX)

    return light_brightness_pct

def get_desired_light_brightness_pct(direction, current_light_brightness_pct, light_brightness_pct_step):
    log.debug(f"current light brightness: {current_light_brightness_pct}%")

    # choose rounding method
    rounding_method = None
    if direction == DIM_DOWN:
        rounding_method = math.ceil
    elif direction == DIM_UP:
        rounding_method = math.floor

    # figure out how many whole brightness steps we have
    whole_brightness_step = rounding_method(current_light_brightness_pct / light_brightness_pct_step)
    log.debug(f"number of whole steps rounded for dimming: {whole_brightness_step}")

    # start desired brightness at nearest whole brightness step for dimming
    desired_light_brightness_pct = whole_brightness_step * light_brightness_pct_step
    log.debug(f"desired brightness rounded to nearest whole step for dimming: {desired_light_brightness_pct}%")

    # dim up/down by brightness step
    desired_light_brightness_pct = desired_light_brightness_pct + (light_brightness_pct_step * direction)
    log.debug(f"desired brightness dimmed by brightness step: {desired_light_brightness_pct}%")

    SWITCH_DIM_MAX_PCT = 100
    SWITCH_DIM_MIN_PCT = 1
    # SWITCH_DIM_UP_POWER_ON

    if direction == DIM_DOWN:
        if current_light_brightness_pct <= SWITCH_DIM_MIN_PCT:
            desired_light_brightness_pct = LIGHT_BRIGHTNESS_PCT_MIN
        elif current_light_brightness_pct <= light_brightness_pct_step:
            desired_light_brightness_pct = SWITCH_DIM_MIN_PCT
    elif direction == DIM_UP:
        if current_light_brightness_pct == LIGHT_BRIGHTNESS_PCT_MIN:
            desired_light_brightness_pct = SWITCH_DIM_MIN_PCT
        else:
            desired_light_brightness_pct = min(desired_light_brightness_pct, SWITCH_DIM_MAX_PCT)

    return desired_light_brightness_pct

pico_event_triggers = []

def pico_event_trigger_factory(pico_device_id):

    """
    # sample event captured through UI

    event_type: lutron_caseta_button_event
    data:
        serial: 48582338
        type: Pico3ButtonRaiseLower
        button_number: 4
        leap_button_number: 2
        device_name: Recessed Light
        device_id: eb9d6926898607fe50f57cfd84e6aec0
        area_name: Entryway
        button_type: "off"
        action: release
        origin: LOCAL
        time_fired: "2023-08-25T15:57:54.841371+00:00"
    context:
        id: 01H8PPN5RS0ANMG84472T319XN
        parent_id: null
        user_id: null
    """

    @event_trigger("lutron_caseta_button_event", 
                    f"type == 'Pico3ButtonRaiseLower' \
                    and device_id == '{pico_device_id}' \
                    and action == 'press'")
    def pico_event_trigger(**kwargs):
        pico_device_id   = kwargs['device_id']
        pico_button_type = kwargs['button_type']
        light_entity_id  = pyscript.app_config['pico_light_mapping'][pico_device_id]['light_entity_id']
        app_entity_id    = f"{APP_DOMAIN}.{light_entity_id.split('.', 1)[1]}"

        app_state_old_variable = None
        app_state_old_attributes = state.getattr(app_entity_id)
        
        app_state_new_attributes = {}

        if app_state_old_attributes is None:
            app_state_old_attributes = {}

        # Turn On Light
        if pico_button_type == PICO_ACTION_ON:
            light.turn_on(entity_id=light_entity_id)

        # Switch Light Scene
        elif pico_button_type == PICO_ACTION_STOP:
            pico_scene_number = PICO_DEFAULT_SCENE_NUMBER

            if 'pico_scene_number' in app_state_old_attributes:
                pico_scene_number = app_state_old_attributes['pico_scene_number']

            # iterate through pico scene array
            pico_scene_number = pico_scene_number + 1
            pico_scene_number = pico_scene_number % len(PICO_DEFAULT_SCENES)

            light.turn_on(entity_id=light_entity_id, **PICO_DEFAULT_SCENES[pico_scene_number])

            app_state_new_attributes['pico_scene_number'] = pico_scene_number

        # Turn Off Light
        elif pico_button_type == PICO_ACTION_OFF:
            light.turn_off(entity_id=light_entity_id)

        # Dim the Light
        elif pico_button_type in [PICO_ACTION_RAISE, PICO_ACTION_LOWER]:
            direction = None

            if pico_button_type == PICO_ACTION_RAISE:
                direction = DIM_UP
            elif pico_button_type == PICO_ACTION_LOWER:
                direction = DIM_DOWN

            light_brightness_pct = get_light_brightness_pct(light_entity_id)
            desired_light_brightness_pct = get_desired_light_brightness_pct(direction, light_brightness_pct, PICO_DEFAULT_BRIGHTNESS_PCT)

            light.turn_on(entity_id=light_entity_id, brightness_pct=desired_light_brightness_pct)

        # write current state
        app_state_new_attributes['pico_action'] = pico_button_type
        state.set(app_entity_id, value=time.time(), new_attributes=app_state_new_attributes)

        # TO DO
        #  add pico brightness percentage

    return pico_event_trigger

for pico_device_id in pyscript.app_config['pico_light_mapping']:
    pico_event_triggers.append(pico_event_trigger_factory(pico_device_id))
