from threading import Lock
import json
import numpy as np
import pandas as pd

class NumpyEncoder(json.JSONEncoder):
    """ Custom encoder for numpy data types """
    def default(self, obj):
        if isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
                            np.int16, np.int32, np.int64, np.uint8,
                            np.uint16, np.uint32, np.uint64)):

            return int(obj)

        elif isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
            return float(obj)

        elif isinstance(obj, (np.complex_, np.complex64, np.complex128)):
            return {'real': obj.real, 'imag': obj.imag}

        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()

        elif isinstance(obj, (np.bool_)):
            return bool(obj)

        elif isinstance(obj, (np.void)): 
            return None

        return json.JSONEncoder.default(self, obj)
    
###################################
# To create map file from diagram #
###################################

def codebook (code_num):
    if code_num==1:
        return "wall"
    elif code_num==2:
        return "door"
    elif code_num==3:
        return "green"
    elif code_num==4:
        return "yellow"    
    elif code_num==5:
        return "red"
    elif code_num==6:
        return "engineer_1"
    elif code_num == 7:
        return "engineer_0"
    elif code_num==8:
        return "medic_1"
    elif code_num == 9:
        return "medic_0"
    elif code_num==10:
        return "rubble"
    elif code_num==11:
        # return "left_pane"
        # return "center_pane"
        return ""

    
def process_map():
    # df_map = pd.read_csv('mission/static/data/map_new_design.csv')
    df_map = pd.read_csv('static/data/map_design_small_2.csv')
    new_map = pd.melt(df_map, id_vars='x/z', value_vars=[str(i) for i in range(0,int(list(df_map)[-1]) + 1)], var_name='z', value_name='key')
    new_map = new_map.rename(columns={"x/z": "x"})
    new_map.index.name='id'
    new_map['key2'] = new_map.apply(lambda x: codebook(x['key']), axis=1)
    new_map.columns = ['z', 'x', 'code', 'key']
    new_map[['key', 'human']] = new_map['key'].str.split('_', expand = True)
    new_map['human'] = pd.to_numeric(new_map['human'])
    for i in range(6, 11):
        new_map.to_csv(f'static/maps/map_{i}.csv')