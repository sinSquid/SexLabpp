-- Resolve all script-name tokens conservatively, including property/parameter
-- types as well as explicit imports and inheritance. First include wins, just
-- as it does for PapyrusCompiler. Cycles are normal for mutually used types.
function build_index(includedirs)
    local index = {}
    for _, dir in ipairs(includedirs) do
        for _, file in ipairs(os.files(path.join(dir, "*.psc"))) do
            local name = path.basename(file):lower()
            if not index[name] then
                index[name] = path.normalize(path.absolute(file))
            end
        end
    end
    return {paths = index, references = {}}
end

function main(sourcefile, index)
    local files, visited = {}, {}
    local function visit(file)
        file = path.normalize(path.absolute(file))
        local key = file:lower()
        if visited[key] then
            return
        end
        visited[key] = true
        table.insert(files, file)
        local references = index.references[key]
        if not references then
            references = {}
            local unique = {}
            local source = io.readfile(file) or ""
            for token in source:gmatch("[%a_][%w_]*") do
                local dependency = index.paths[token:lower()]
                if dependency and not unique[dependency] then
                    unique[dependency] = true
                    table.insert(references, dependency)
                end
            end
            index.references[key] = references
        end
        for _, dependency in ipairs(references) do
            visit(dependency)
        end
    end
    visit(sourcefile)
    table.sort(files)
    return files
end
