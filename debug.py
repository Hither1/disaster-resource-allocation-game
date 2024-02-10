from omegaconf import OmegaConf

def load_config(config_path, config_name):
    with open(f"{config_path}/{config_name}.yaml", "r") as file:
        return OmegaConf.load(file)

if __name__ == "__main__":
    config1 = load_config("configs", "sac")
    config2 = load_config("configs", "leadtimes")

    merged_config = OmegaConf.merge(config1, config2)
    print("Merged configuration:")
    print(OmegaConf.to_yaml(merged_config))
