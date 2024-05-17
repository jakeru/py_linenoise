# -----------------------------------------------------------------------------
"""
Utility Functions
"""
# -----------------------------------------------------------------------------

inv_arg = "invalid argument\n"


def int_arg(ui, arg, limits, base):
    """convert a number string to an integer, or None"""
    try:
        val = int(arg, base)
    except ValueError:
        ui.put(inv_arg)
        return None
    if (val < limits[0]) or (val > limits[1]):
        ui.put(inv_arg)
        return None
    return val


# -----------------------------------------------------------------------------


def display_cols(clist, csize=None):
    """
    return a string for a list of columns
    each element in clist is [col0_str, col1_str, col2_str, ...]
    csize is a list of column width minimums
    """
    if len(clist) == 0:
        return ""
    # how many columns?
    ncols = len(clist[0])
    # make sure we have a well formed csize
    if csize is None:
        csize = [
            0,
        ] * ncols
    else:
        assert len(csize) == ncols
    # convert any "None" items to ''
    for l in clist:
        assert len(l) == ncols
        for i in range(ncols):
            if l[i] is None:
                l[i] = ""
    # additional column margin
    cmargin = 1
    # go through the strings and bump up csize widths if required
    for l in clist:
        for i in range(ncols):
            if csize[i] <= len(l[i]):
                csize[i] = len(l[i]) + cmargin
    # build the format string
    fmts = []
    for n in csize:
        fmts.append("%%-%ds" % n)
    fmt = "".join(fmts)
    # generate the string
    s = [(fmt % tuple(l)) for l in clist]
    return "\n".join(s)


# -----------------------------------------------------------------------------
