#!/usr/bin/env python3
"""Build a small ESM3 addon and original placeholder geometry from source."""
from pathlib import Path
import argparse
import struct

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/data'
TEMPLATE = ROOT / '.runtime/example-suite'


def sub(tag, data):
    if isinstance(data, str):
        data = data.encode('utf-8') + b'\0'
    return struct.pack('<4sI', tag.encode(), len(data)) + data


def record(tag, data):
    return struct.pack('<4sIII', tag.encode(), len(data), 0, 0) + data


def records(path):
    data = path.read_bytes()
    offset = 0
    while offset < len(data):
        tag, size, _, _ = struct.unpack_from('<4sIII', data, offset)
        yield tag.decode(), data[offset + 16:offset + 16 + size]
        offset += 16 + size
    if offset != len(data):
        raise ValueError('Truncated content file')


def subs(data):
    offset = 0
    while offset < len(data):
        tag, size = struct.unpack_from('<4sI', data, offset)
        yield tag.decode(), data[offset + 8:offset + 8 + size]
        offset += 8 + size


def box(path, size, color, center=(0, 0, 0)):
    x, y, z = [s / 2 for s in size]
    vertices = [(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    faces = [((0,3,2,1),(0,0,-1)),((4,5,6,7),(0,0,1)),((0,1,5,4),(0,-1,0)),
             ((1,2,6,5),(1,0,0)),((2,3,7,6),(0,1,0)),((3,0,4,7),(-1,0,0))]
    positions, normals = [], []
    for indices, normal in faces:
        for i in (0,1,2,0,2,3):
            positions.append(' '.join(str(vertices[indices[i]][j]+center[j]) for j in range(3)))
            normals.append(' '.join(map(str, normal)))
    # COLLADA is the documented import path and avoids relying on OSG serializer versions.
    text = '''<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
<asset><created>2026-10-21T00:00:00Z</created><modified>2026-10-21T00:00:00Z</modified><unit name="meter" meter="1"/><up_axis>Z_UP</up_axis></asset>
<library_effects><effect id="effect"><profile_COMMON><technique sid="common"><phong>
<ambient><color>0.3 0.3 0.3 1</color></ambient><diffuse><color>%s</color></diffuse>
</phong></technique></profile_COMMON></effect></library_effects>
<library_materials><material id="material"><instance_effect url="#effect"/></material></library_materials>
<library_geometries><geometry id="box"><mesh>
<source id="positions"><float_array id="positions-array" count="108">%s</float_array><technique_common><accessor source="#positions-array" count="36" stride="3"><param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/></accessor></technique_common></source>
<source id="normals"><float_array id="normals-array" count="108">%s</float_array><technique_common><accessor source="#normals-array" count="36" stride="3"><param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/></accessor></technique_common></source>
<vertices id="vertices"><input semantic="POSITION" source="#positions"/></vertices>
<triangles count="12" material="surface"><input semantic="VERTEX" source="#vertices" offset="0"/><input semantic="NORMAL" source="#normals" offset="1"/><p>%s</p></triangles>
</mesh></geometry></library_geometries>
<library_visual_scenes><visual_scene id="scene"><node id="mesh" name="mesh"><instance_geometry url="#box"><bind_material><technique_common><instance_material symbol="surface" target="#material"/></technique_common></bind_material></instance_geometry></node></visual_scene></library_visual_scenes>
<scene><instance_visual_scene url="#scene"/></scene></COLLADA>
''' % (' '.join(map(str,color)), ' '.join(positions), ' '.join(normals),
       ' '.join(str(i) for i in range(36) for _ in range(2)))
    path.write_text(text,encoding='utf-8')


def dds(path, color):
    # Uncompressed 4x4 RGBA DDS, with explicit masks and pitch.
    header = [124, 0x100F, 4, 4, 16, 0, 0] + [0]*11
    header += [32, 0x41, 0, 32, 0xFF, 0xFF00, 0xFF0000, 0xFF000000]
    header += [0x1000, 0, 0, 0, 0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'DDS ' + struct.pack('<31I', *header) + bytes(color)*16)


def main(output=None):
    build = Path(output) if output is not None else BUILD
    meshes = build / 'meshes/echo'
    meshes.mkdir(parents=True, exist_ok=True)
    definitions = {
        'floor': ((2200,2200,50),(.075,.09,.14,1),(0,0,-25)),
        'wall': ((2200,70,300),(.13,.15,.22,1),(0,0,150)),
        'pillar': ((90,90,360),(.18,.2,.3,1),(0,0,180)),
        'rune': ((180,180,4),(.08,.65,.9,1),(0,0,3)),
        'blade': ((6,9,100),(.3,.8,1,1),(0,0,35)),
    }
    for name, (size,color,center) in definitions.items():
        box(meshes / (name+'.dae'),size,color,center)
    box(meshes/'empty.dae',(.001,.001,.001),(0,0,0,0))
    dds(build/'textures/echo/white.dds',(255,255,255,255))
    dds(build/'textures/hu_male.dds',(112,160,195,255))
    dds(build/'textures/menu_icon_equip.dds',(90,200,255,255))
    for name in ('top','bottom','vert'):
        dds(build/f'textures/menu_small_energy_bar_{name}.dds',(40,76,110,255))

    contents = []
    for name in definitions:
        if name == 'blade':
            wpdt = struct.pack('<fihHffH6Bi', 1,0,2,1000,1.5,1.6,0, 1,1,1,1,1,1,0)
            contents.append(record('WEAP',sub('NAME','eh_blade')+sub('MODL','echo/blade.dae')+
                                   sub('FNAM','Echo Blade')+sub('WPDT',wpdt)))
        else:
            contents.append(record('STAT',sub('NAME','eh_'+name)+sub('MODL','echo/'+name+'.dae')))
    for key,value in {'FontColor_color_header':'105,205,255','FontColor_color_normal':'225,235,245'}.items():
        contents.append(record('GMST', sub('NAME',key)+sub('STRV',value)))

    # Give the template player complete stats and remove the sample's nonexistent spell.
    for tag,data in records(TEMPLATE/'game_template/data/template.omwgame'):
        fields = list(subs(data))
        if tag == 'NPC_' and dict(fields).get('NAME',b'').lower().rstrip(b'\0') == b'player':
            result = []
            for key,value in fields:
                if key == 'NPCS':
                    continue
                if key == 'FNAM':
                    value = b'Echo Hunter\0'
                if key == 'NPDT':
                    value = bytearray(value)
                    # 2-byte level + 8 attributes + 27 skills + one padding byte.
                    struct.pack_into('<HHH', value, 38, 120,100,1000)
                    value[2:10] = bytes([50,50,50,50,75,50,50,50])
                result.append(sub(key,value))
            if 'FNAM' not in dict(fields):
                result.append(sub('FNAM','Echo Hunter'))
            contents.append(record(tag,b''.join(result)))

    base_creature = next(d for t,d in records(TEMPLATE/'example_animated_creature/data/landracer.omwaddon') if t=='CREA')
    for identifier,name,hp,scale in [('eh_guard','Rift Stalker',70,1),('eh_boss','Warden of the Rift',360,1.8)]:
        result=[]
        for key,value in subs(base_creature):
            if key=='NAME': value=(identifier+'\0').encode()
            if key=='FNAM': value=(name+'\0').encode()
            if key=='NPDT':
                value=bytearray(value)
                struct.pack_into('<i',value,40,hp)
                struct.pack_into('<i',value,44,100)
                struct.pack_into('<i',value,48,1000)
                struct.pack_into('<i',value,24,45) # speed attribute
            if key=='AIDT': value=bytes(len(value)) # custom Lua owns combat
            if key=='XSCL': value=struct.pack('<f',scale)
            result.append(sub(key,value))
        if 'XSCL' not in dict(subs(base_creature)):
            result.append(sub('XSCL',struct.pack('<f',scale)))
        contents.append(record('CREA',b''.join(result)))

    cell=sub('NAME','Echo Arena')+sub('DATA',struct.pack('<iii',1,0,0))
    cell+=sub('AMBI',struct.pack('<IIIf',0xFF655C50,0xFFB8AEA0,0xFF28180F,0.4))
    placements=[('floor',0,0,0,0),('wall',0,1100,0,0),('wall',0,-1100,0,0),
                ('wall',1100,0,0,1.5707963),('wall',-1100,0,0,1.5707963)]
    placements += [('pillar',x,y,0,0) for x,y in [(-800,-800),(800,-800),(-800,800),(800,800)]]
    placements += [('rune',x,y,0,0) for x,y in [(-650,0),(650,0),(0,650)]]
    for index,(name,x,y,z,yaw) in enumerate(placements,1):
        cell+=sub('FRMR',struct.pack('<I',index))+sub('NAME','eh_'+name)
        cell+=sub('DATA',struct.pack('<6f',x,y,z,0,0,yaw))
    contents.append(record('CELL',cell))
    header=sub('HEDR',struct.pack('<fi32s256si',1.3,0,b'Echo Hunter',b'Original standalone action prototype',len(contents)))
    master=TEMPLATE/'game_template/data/template.omwgame'
    header+=sub('MAST','template.omwgame')+sub('DATA',struct.pack('<Q',master.stat().st_size))
    (build/'echo.omwaddon').write_bytes(record('TES3',header)+b''.join(contents))
    print('Built Echo Arena, original geometry and actor records.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=BUILD)
    main(parser.parse_args().output)
