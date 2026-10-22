function main()
    local files = os.files("xmake/**.lua")
    table.insert(files, "xmake.lua")
    assert(#files >= 14, "Incomplete Lua file discovery")
    for _, file in ipairs(files) do
        assert(loadfile(file), "Invalid Lua syntax: " .. file)
    end
    local source = io.readfile("xmake/papyrus/project.lua")
    local helper = assert(source:match("(local function xml%b()%s*.-\n    end)"))
    local xml = assert(load(helper .. "\nreturn xml"))()
    assert(xml("a&b<c>d\"e'f") == "a&amp;b&lt;c&gt;d&quot;e&apos;f")
    assert(xml("normal/path") == "normal/path")
    print("PASS: " .. #files .. " Lua files parsed; project XML escaping")
end
