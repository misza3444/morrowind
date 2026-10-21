#!/usr/bin/env python3
"""Build a small ESM3 addon and original placeholder geometry from source."""
from pathlib import Path
import argparse
import hashlib
import json
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


def stage_assets(build):
    manifest = json.loads((ROOT/'assets/manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        source = TEMPLATE/item['source']
        error = 'Missing or modified art asset; run tools/setup.py: ' + item['source']
        if not source.is_file():
            raise RuntimeError(error)
        data = source.read_bytes()
        if source.suffix.lower() == '.dae' and hashlib.sha256(data).hexdigest() != item['sha256']:
            # Git for Windows may convert XML models to CRLF on checkout.
            # Restore upstream LF bytes only when their pinned digest matches.
            data = data.replace(b'\r\n', b'\n')
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise RuntimeError(error)
        target = build/item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (build/'asset-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')


def box(path, size, color, center=(0, 0, 0), texture=None, tiles=1):
    x, y, z = [s / 2 for s in size]
    vertices = [(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    faces = [((0,3,2,1),(0,0,-1)),((4,5,6,7),(0,0,1)),((0,1,5,4),(0,-1,0)),
             ((1,2,6,5),(1,0,0)),((2,3,7,6),(0,1,0)),((3,0,4,7),(-1,0,0))]
    positions, normals, texcoords = [], [], []
    for indices, normal in faces:
        for corner in (0,1,2,0,2,3):
            i = indices[corner]
            positions.append(' '.join(str(vertices[i][j]+center[j]) for j in range(3)))
            normals.append(' '.join(map(str, normal)))
            texcoords.append(' '.join(map(str, ((0,0),(tiles,0),(tiles,tiles),(0,tiles))[corner])))
    images = parameters = ''
    diffuse = '<color>'+' '.join(map(str,color))+'</color>'
    if texture:
        images = '<library_images><image id="surface-image"><init_from>'+texture+'</init_from></image></library_images>'
        parameters = '<newparam sid="surface"><surface type="2D"><init_from>surface-image</init_from></surface></newparam><newparam sid="surface-sampler"><sampler2D><source>surface</source></sampler2D></newparam>'
        diffuse = '<texture texture="surface-sampler" texcoord="UVMap"/>'
    # COLLADA is the documented import path and avoids relying on OSG serializer versions.
    text = '''<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
<asset><created>2026-10-21T00:00:00Z</created><modified>2026-10-21T00:00:00Z</modified><unit name="meter" meter="1"/><up_axis>Z_UP</up_axis></asset>
%s<library_effects><effect id="effect"><profile_COMMON>%s<technique sid="common"><phong>
<ambient><color>0.3 0.3 0.3 1</color></ambient><diffuse>%s</diffuse>
</phong></technique></profile_COMMON></effect></library_effects>
<library_materials><material id="material"><instance_effect url="#effect"/></material></library_materials>
<library_geometries><geometry id="box"><mesh>
<source id="positions"><float_array id="positions-array" count="108">%s</float_array><technique_common><accessor source="#positions-array" count="36" stride="3"><param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/></accessor></technique_common></source>
<source id="normals"><float_array id="normals-array" count="108">%s</float_array><technique_common><accessor source="#normals-array" count="36" stride="3"><param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/></accessor></technique_common></source>
<source id="uv"><float_array id="uv-array" count="72">%s</float_array><technique_common><accessor source="#uv-array" count="36" stride="2"><param name="S" type="float"/><param name="T" type="float"/></accessor></technique_common></source>
<vertices id="vertices"><input semantic="POSITION" source="#positions"/></vertices>
<triangles count="12" material="surface"><input semantic="VERTEX" source="#vertices" offset="0"/><input semantic="NORMAL" source="#normals" offset="1"/><input semantic="TEXCOORD" source="#uv" offset="2" set="0"/><p>%s</p></triangles>
</mesh></geometry></library_geometries>
<library_visual_scenes><visual_scene id="scene"><node id="mesh" name="mesh"><instance_geometry url="#box"><bind_material><technique_common><instance_material symbol="surface" target="#material"><bind_vertex_input semantic="UVMap" input_semantic="TEXCOORD" input_set="0"/></instance_material></technique_common></bind_material></instance_geometry></node></visual_scene></library_visual_scenes>
<scene><instance_visual_scene url="#scene"/></scene></COLLADA>
''' % (images, parameters, diffuse, ' '.join(positions), ' '.join(normals), ' '.join(texcoords),
       ' '.join(str(i) for i in range(36) for _ in range(3)))
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
    stage_assets(build)
    definitions = {
        'floor': ((2200,2200,50),(.075,.09,.14,1),(0,0,-25)),
        'wall': ((2200,70,300),(.13,.15,.22,1),(0,0,150)),
        'rune': ((180,180,4),(.08,.65,.9,1),(0,0,3)),
    }
    for name, (size,color,center) in definitions.items():
        box(meshes / (name+'.dae'),size,color,center,
            texture='textures/ground/road_01.dds' if name == 'floor' else None, tiles=8)
    box(meshes/'empty.dae',(.001,.001,.001),(0,0,0,0))
    dds(build/'textures/echo/white.dds',(255,255,255,255))
    dds(build/'textures/hu_male.dds',(112,160,195,255))
    dds(build/'textures/menu_icon_equip.dds',(90,200,255,255))
    for name in ('top','bottom','vert'):
        dds(build/f'textures/menu_small_energy_bar_{name}.dds',(40,76,110,255))

    contents = []
    for name in definitions:
        contents.append(record('STAT',sub('NAME','eh_'+name)+sub('MODL','echo/'+name+'.dae')))
    wpdt = struct.pack('<fihHffH6Bi', 1,0,2,1000,1.5,1.6,0, 1,1,1,1,1,1,0)
    contents.append(record('WEAP',sub('NAME','eh_blade')+sub('MODL','weapons/basic_sword2h.dae')+
                           sub('FNAM','Echo Blade')+sub('WPDT',wpdt)))
    for name, model in {
        'pillar': 'architecture/HubTemple_Pillar01.dae',
        'gate': 'architecture/HubTemple_DoorFrame01.dae',
        'chest': 'containers/Hub_Chest01.dae',
        'weapon_stand': 'architecture/Hub_WeaponStand01.dae',
        'display_sword': 'weapons/basic_sword2h.dae',
        'display_axe': 'weapons/basic_axe1h.dae',
        'barrel': 'the_barrel.dae',
    }.items():
        contents.append(record('STAT',sub('NAME','eh_'+name)+sub('MODL',model)))
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
    placements += [('pillar',x,y,37.107,0) for x in (-800,800) for y in (-800,0,800)]
    placements += [('rune',x,y,0,0) for x,y in [(-650,0),(650,0),(0,650)]]
    placements += [('gate',0,y,171.092,0) for y in (-1040,1040)]
    placements += [('chest',x,600,0,0) for x in (-925,925)]
    placements += [('weapon_stand',x,-550,4.4,0) for x in (-930,930)]
    placements += [('display_sword',-930,-540,80,0),('display_axe',930,-540,80,0)]
    placements += [('barrel',x,y,0,0) for x,y in [(-930,-300),(-850,-350),(930,300)]]
    for index,(name,x,y,z,yaw) in enumerate(placements,1):
        cell+=sub('FRMR',struct.pack('<I',index))+sub('NAME','eh_'+name)
        pitch = 1.5707963 if name.startswith('display_') else 0
        cell+=sub('DATA',struct.pack('<6f',x,y,z,pitch,0,yaw))
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
