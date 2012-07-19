from django.contrib.gis.db import models
from django.contrib.gis.gdal import Envelope
from django.db.models import signals

from geonode.maps.models import Layer
from geonode.maps.models import Map
from geonode.maps.models import map_changed_signal
from geonode.simplesearch import util

from logging import getLogger

_logger = getLogger(__name__)

class SpatialTemporalIndex(models.Model):
    time_start = models.BigIntegerField(null=True)
    time_end = models.BigIntegerField(null=True)
    extent = models.PolygonField()
    objects = models.GeoManager() 
    
    class Meta:
        abstract = True
        
    def __unicode__(self):
        return '<SpatialTemporalIndex> for %s, %s, %s - %s' % (
            self.indexed,
            self.extent.extent,
            util.jdate_to_approx_iso_str(self.time_start),
            util.jdate_to_approx_iso_str(self.time_end)
        )
    
class LayerIndex(SpatialTemporalIndex):
    indexed = models.OneToOneField(Layer,related_name='spatial_temporal_index')
    
class MapIndex(SpatialTemporalIndex):
    indexed = models.OneToOneField(Map,related_name='spatial_temporal_index')
    
def filter_by_period(index, start, end):
    q = index.objects.all()
    if start:
        q = q.filter(time_start__gte = util.iso_str_to_jdate(start))
    if end:
        q = q.filter(time_end__lte = util.iso_str_to_jdate(end))
    return q

def index_object(obj, update=False):
    if type(obj) == Layer:
        index = LayerIndex
        func = index_layer
    elif type(obj) == Map:
        index = MapIndex
        func = index_map
    else:
        raise Exception('cannot index %s' % obj)
    
    created = False
    try:
        index_obj = index.objects.get(indexed=obj)
    except index.DoesNotExist:
        _logger.debug('created index for %s',obj)
        index_obj = index(indexed=obj)
        created = True
    
    if not update or created:
        _logger.debug('indexing %s',obj)
        try:
            func(index_obj, obj)
        except:
            _logger.exception('Error indexing object %s', obj)
    else:
        _logger.debug('skipping %s',obj)
        
def index_layer(index, obj):
    start = end = None
    try:
        start, end = obj.get_time_extent()
    except:
        _logger.warn('could not get time info for %s', obj.typename)
    
    if start:
        index.time_start = util.iso_str_to_jdate(start)
    if end:
        index.time_end = util.iso_str_to_jdate(end)
        
    try:
        wms_metadata = obj.metadata()
    except:
        _logger.warn('could not get WMS info for %s', obj.typename)
        return
    
    min_x, min_y, max_x, max_y = wms_metadata.boundingBoxWGS84
    
    if wms_metadata.boundingBoxWGS84 != (0.0,0.0,-1.0,-1.0):
        try:
            index.extent = Envelope(min_x,min_y,max_x,max_y).wkt;
        except Exception,ex:
            _logger.warn('Error computing envelope: %s, bounding box was %s', str(ex),wms_metadata.boundingBoxWGS84)
        index.save()
    else:
        _logger.warn('Bounding box empty, not indexing')
    
def index_map(index, obj):
    time_start = None
    time_end = None
    extent = Envelope(0,0,0,0)
    for l in obj.local_layers:
        start = end = None
        try:
            start, end = l.get_time_extent()
        except:
            _logger.warn('could not get time info for %s', l.typename)

        if start:
            start = util.iso_str_to_jdate(start)
            if time_start is None:
                time_start = start
            else:
                time_start = min(time_start, start)
        if end:
            end = util.iso_str_to_jdate(end)
            if time_end is None:
                time_end = start
            else:
                time_end = max(time_end, end)
            
        try:
            wms_metadata = l.metadata()
            extent.expand_to_include(wms_metadata.boundingBoxWGS84)
        except:
            _logger.warn('could not get WMS info for %s', l.typename )
                
    if time_start:
        index.time_start = time_start
    if time_end:
        index.time_end = time_end
    index.extent = extent.wkt
    index.save()
        
def object_created(instance, sender, **kw):
    if kw['created']:
        index_object(instance)
        
def map_updated(sender, **kw):
    if kw['what_changed'] == 'layers':
        index_object(sender)
        
def object_deleted(instance, sender, **kw):
    if type(instance) == Layer:
        index = LayerIndex
    elif type(instance) == Map:
        index = MapIndex
    try:
        index.objects.get(indexed=instance).delete()
    except index.DoesNotExist:
        pass
        
signals.post_save.connect(object_created, sender=Layer)

signals.pre_delete.connect(object_deleted, sender=Map)
signals.pre_delete.connect(object_deleted, sender=Layer)

map_changed_signal.connect(map_updated)