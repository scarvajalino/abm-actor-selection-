"""Paired estimates and approximate simultaneous bands for prespecified contrasts."""
import numpy as np
from pilot_metrics import estimate


def simultaneous_primary(differences,indices):
    values=np.asarray(differences,dtype=float)
    if values.ndim!=2 or not np.isfinite(values).all():raise ValueError('Complete paired finite differences required')
    n=values.shape[0]
    means=values.mean(axis=0)
    se=values.std(axis=0,ddof=1)/np.sqrt(n)
    counts=np.stack([np.bincount(row,minlength=n) for row in indices])/n
    boot=counts@values
    active=se>0
    max_dev=np.max(np.abs((boot[:,active]-means[active])/se[active]),axis=1) if active.any() else np.zeros(len(indices))
    critical=float(np.quantile(max_dev,.95))
    return {'mean':means,'mcse':se,'low':means-critical*se,'high':means+critical*se,
            'critical':critical,'zero_sample_variance':~active}


def descriptive(values,indices):
    result=estimate(values,indices)
    finite=np.asarray(values,dtype=float);finite=finite[np.isfinite(finite)]
    result.update({name:float(np.quantile(finite,q)) if len(finite) else None
        for name,q in [('median',.5),('q05',.05),('q25',.25),('q75',.75),('q95',.95)]})
    result['iqr']=result['q75']-result['q25'] if len(finite) else None
    return result
