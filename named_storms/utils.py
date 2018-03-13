from named_storms.data.processors import GridProcessor, SequenceProcessor
from named_storms.models import PROCESSOR_DATA_TYPE_GRID, PROCESSOR_DATA_TYPE_SEQUENCE, CoveredDataProvider


def processor_class(provider: CoveredDataProvider):
    if provider.data_type == PROCESSOR_DATA_TYPE_GRID:
        return GridProcessor
    elif provider.data_type == PROCESSOR_DATA_TYPE_SEQUENCE:
        return SequenceProcessor
    else:
        raise Exception('no processor class found for data type %s' % provider.data_type)
