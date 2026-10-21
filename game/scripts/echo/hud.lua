local ui = require('openmw.ui')
local util = require('openmw.util')
local M = {}
local element
local white = ui.texture {path = 'textures/echo/white.dds'}
local colors = {
    white = util.color.rgb(0.88,0.94,1), blue = util.color.rgb(0.23,0.72,1),
    dark = util.color.rgb(0.025,0.04,0.075), muted = util.color.rgb(0.53,0.64,0.75),
    red = util.color.rgb(0.95,0.29,0.36), gold = util.color.rgb(1,0.78,0.35),
}

local function text(value,x,y,size,color)
    return {type = ui.TYPE.Text, props = {text = value, position = util.vector2(x,y),
        textSize = size, textColor = color or colors.white, textShadow = true}}
end
local function rect(x,y,w,h,color)
    return {type = ui.TYPE.Image, props = {position = util.vector2(x,y), size = util.vector2(w,h),
        resource = white, color = color}}
end

function M.update(data)
    local content = {
        rect(20,20,340,102,colors.dark),
        text('ŁOWCA ECHA',36,30,22,colors.blue),
        text(string.format('HP  %d / %d',math.ceil(data.hp),data.maxHp),36,62,17),
        rect(36,93,300,7,colors.muted),
        rect(36,93,300*math.max(0,data.hp/data.maxHp),7,colors.blue),
        text('SZCZELINA 01  /  ARENA',20,140,16,colors.muted),
        text('Pokonaj strażników i władcę szczeliny.',20,166,16),
        text('Echa: '..data.reward,20,194,16,colors.gold),
    }
    local size = ui.screenSize()
    content[#content+1] = rect(20,size.y-94,700,72,colors.dark)
    local function ready(value) return value > 0 and string.format('%.1fs',value) or 'GOTOWE' end
    content[#content+1] = text('LPM  Combo    SPACJA  Unik    TAB  Namierz',36,size.y-84,16)
    content[#content+1] = text('Q  Rozcięcie: '..ready(data.cooldowns.cleave)..'    E  Nova: '..ready(data.cooldowns.nova),36,size.y-58,16,colors.blue)
    if data.target then
        content[#content+1] = text(data.target.name, size.x/2-150,24,20,colors.red)
        content[#content+1] = rect(size.x/2-150,56,300,7,colors.muted)
        content[#content+1] = rect(size.x/2-150,56,300*math.max(0,data.target.hp/data.target.maxHp),7,colors.red)
    end
    if data.notice and data.notice ~= '' then
        content[#content+1] = text(data.notice,size.x/2-180,size.y/2-80,24,colors.gold)
    end
    if data.phase ~= 'active' then
        content[#content+1] = rect(size.x/2-230,size.y/2-30,460,92,colors.dark)
        content[#content+1] = text(data.phase == 'victory' and 'SZCZELINA OCZYSZCZONA  +1 ECHO' or 'WYPRAWA ZAKOŃCZONA',size.x/2-210,size.y/2-15,19,colors.gold)
        content[#content+1] = text('R — rozpocznij kolejną wyprawę',size.x/2-210,size.y/2+20,17)
    end
    local layout = {type = ui.TYPE.Widget,layer = 'HUD',props = {relativeSize = util.vector2(1,1)},content = ui.content(content)}
    if element then element.layout = layout; element:update() else element = ui.create(layout) end
end

function M.destroy()
    if element then element:destroy(); element = nil end
end
return M
