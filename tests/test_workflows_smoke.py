from workflows import (
    app_events_translate,
    app_info,
    copy,
    export_localizations,
    full_setup,
    game_center_localizations,
    iap_translate,
    manage_presets,
    promo,
    release,
    subscription_translate,
    translate,
    update_localizations,
)


def test_workflow_cancel_paths_return_true(fake_cli):
    fake_cli.ui.app_id = None

    workflows = [
        translate.run,
        release.run,
        promo.run,
        update_localizations.run,
        copy.run,
        full_setup.run,
        app_info.run,
        export_localizations.run,
        manage_presets.run,
        iap_translate.run,
        subscription_translate.run,
        game_center_localizations.run,
        app_events_translate.run,
    ]

    for run_fn in workflows:
        assert run_fn(fake_cli) is True
