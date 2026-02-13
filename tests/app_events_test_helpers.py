def make_event(event_id="event1", primary="en-US"):
    return {
        "id": event_id,
        "attributes": {
            "referenceName": "Season Event",
            "eventState": "ACTIVE",
            "badge": "LIVE",
            "primaryLocale": primary,
        },
    }


def make_event_loc(loc_id, locale, name="Name", short="Short", long="Long text"):
    return {
        "id": loc_id,
        "type": "appEventLocalizations",
        "attributes": {
            "locale": locale,
            "name": name,
            "shortDescription": short,
            "longDescription": long,
        },
    }
