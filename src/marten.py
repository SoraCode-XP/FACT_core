from config import cfg, load_config

if __name__ == '__main__':
    load_config()
    from pprint import pprint
    pprint(cfg)
