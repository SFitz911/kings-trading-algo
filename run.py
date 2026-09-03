"""Entry point for the dashboard: python run.py"""
from kings_algo.config import load_config
from kings_algo.gui import Dashboard

if __name__ == "__main__":
    Dashboard(load_config()).mainloop()
