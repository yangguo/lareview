
def get_allsubstring(test_str):
    # Get all substrings of string
    # Using list comprehension + string slicing
    res = [test_str[i: j] for i in range(len(test_str))
              for j in range(i + 1, len(test_str) + 1)]
    res1=[x for x in res if len(x)>1]
    return res1


# find duplicate userid
def find_duplicate_userid(userls):
    # get unique userid
    userid=list(set(userls))
    # get duplicate userid
    subdict=dict()
    for uid in userid:
        subdict[uid]=[]
        for idx, user in enumerate(userls):
    #         print(userid)
            if user in uid:
                subdict[uid].append(idx)
    
    result=dict()
    for j,k in subdict.items():
        if len(k)>1:
            result[j]=k
    return result