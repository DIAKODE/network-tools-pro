import os
import sys

from core.win_audio import SingleInstanceManager, set_app_user_model_id
from ui.main_window import NetworkToolsApp


def main():
    set_app_user_model_id("diako.networktools.pro.v61")

    instance_mgr = SingleInstanceManager()
    if instance_mgr.already_running:
        sys.exit(0)

    app = NetworkToolsApp(instance_mgr=instance_mgr)
    app.mainloop()


if __name__ == "__main__":
    main()