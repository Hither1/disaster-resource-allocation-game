# AORPO: Model-based Multi-agent Policy Optimization with Adaptive Opponent-wise Rollouts

This is an official pytorch implementation of the paper [Model-based Multi-agent Policy Optimization with Adaptive Opponent-wise Rollouts](https://arxiv.org/abs/2105.03363).

**Note: We re-factor the code and the results are slightly different with those in the paper.**

## How to Install

```shell
git clone git@github.com:Leo-xh/AORPO.git
cd aorpo
conda create -n aorpo python=3.7
conda activate aorpo

pip install -r requirements.txt
```

## How to Train

We provide a shell script and the command is

```shell
./train.sh [tag] [env_name] [alg] {gpu id}
```

We recomment training with gpus since AORPO is hard to train without gpus.

For example, to train AORPO in Cooperative Navigation

```shell
./train.sh test spread AORPO 0
```

Please feel free to try other parameters.

## Trained Models

Since training AORPO requires plenty of time, we provide trained models (without large dynammics models) in `./trained_models/`, the models can be evaluated using the following command

```shell
python eval.py [env_id] [model_path] {--render}
```

For example, to evaluate AORPO in Cooperative Navigation

```shell
python eval.py simple_spread ./trained_models/simple_spread.pt --render
```

## Citation

```tex
@article{2021,
   title={Model-based Multi-agent Policy Optimization with Adaptive Opponent-wise Rollouts},
   url={http://dx.doi.org/10.24963/ijcai.2021/466},
   DOI={10.24963/ijcai.2021/466},
   journal={Proceedings of the Thirtieth International Joint Conference on Artificial Intelligence},
   publisher={International Joint Conferences on Artificial Intelligence Organization},
   author={Zhang, Weinan and Wang, Xihuai and Shen, Jian and Zhou, Ming},
   year={2021},
   month={Aug} }
```
