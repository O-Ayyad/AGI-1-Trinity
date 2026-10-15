from .coder_interface import prepare_coder_input

def run_coder(state, coder_agent):
    coder_input= prepare_coder_input(state)
    response=coder_agent(coder_input)
    if(isinstance(response,dict) and "code" in response and isinstance(response["code"],str)):
        return {"code": response["code"]}
    else:
       raise ValueError ("Invalid Coder response")