-- Engine-independent combat rules. Time is in simulation seconds.
local M = {}
M.attacks = {
    {duration = 0.60, hit = 0.30, damage = 18, key = 'chop'},
    {duration = 0.56, hit = 0.28, damage = 22, key = 'slash'},
    {duration = 0.68, hit = 0.33, damage = 34, key = 'thrust'},
}
M.skills = {
    cleave = {cooldown = 5, damage = 42, range = 310, cone = 0.1},
    nova = {cooldown = 9, damage = 30, range = 420, cone = -1},
}

function M.new()
    return {phase = 'idle', age = 0, combo = 0, queued = false,
        hit = false, dodgeCooldown = 0, cooldowns = {cleave = 0, nova = 0}}
end

function M.attack(s)
    if s.phase == 'attack' then
        if s.combo < 3 then s.queued = true end
        return false
    end
    if s.phase ~= 'idle' then return false end
    s.phase, s.age, s.combo, s.hit, s.queued = 'attack', 0, 1, false, false
    return true
end

function M.dodge(s)
    if s.phase == 'dodge' or s.dodgeCooldown > 0 then return false end
    s.phase, s.age, s.queued = 'dodge', 0, false
    s.dodgeCooldown = 1.1
    return true
end

function M.invulnerable(s)
    return s.phase == 'dodge' and s.age < 0.24
end

function M.skill(s, key)
    if not M.skills[key] or s.phase ~= 'idle' or s.cooldowns[key] > 0 then return false end
    s.cooldowns[key] = M.skills[key].cooldown
    s.phase, s.age = 'skill', 0
    return true
end

function M.update(s, dt, emit)
    s.dodgeCooldown = math.max(0, s.dodgeCooldown - dt)
    for key, value in pairs(s.cooldowns) do s.cooldowns[key] = math.max(0, value - dt) end
    -- Consume time across state boundaries so low FPS does not lose hit events.
    local remaining = dt
    while remaining > 0 do
        local duration = s.phase == 'attack' and M.attacks[s.combo].duration
            or (s.phase == 'dodge' and 0.34) or (s.phase == 'skill' and 0.55)
        if not duration then break end
        local step = math.min(remaining, duration - s.age)
        s.age = s.age + step
        remaining = remaining - step
        if s.phase == 'attack' and not s.hit and s.age >= M.attacks[s.combo].hit then
            s.hit = true
            emit('hit', M.attacks[s.combo])
        end
        if s.age >= duration then
            if s.phase == 'attack' and s.queued and s.combo < 3 then
                s.combo, s.age, s.hit, s.queued = s.combo + 1, 0, false, false
                emit('animation', M.attacks[s.combo])
            else
                s.phase, s.age, s.combo = 'idle', 0, 0
                emit('idle')
            end
        end
    end
end

return M
