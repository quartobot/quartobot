-- quarto-manubot-cite: Lua-side bridge to pandoc-manubot-cite.
--
-- Quarto extension filters are resolved relative to the extension
-- directory, so declaring an executable filter directly in
-- `_extension.yml` doesn't work — Quarto looks for a file at
-- `_extensions/seandavi/quarto-manubot-cite/pandoc-manubot-cite`
-- and errors out before pandoc gets a chance to find the binary on
-- PATH.
--
-- This Lua filter is a thin bridge: it intercepts the document and
-- pipes it through the `pandoc-manubot-cite` executable (installed by
-- `pip install manubot`). The executable still does all the resolver
-- work; this is just a delegation layer.

local function ensure_parent_dir(path)
  if not path or path == "" then return end
  local parent = pandoc.path.directory(path)
  if not parent or parent == "" or parent == "." then return end
  pandoc.system.make_directory(parent, true)
end

function Pandoc(doc)
  -- Manubot writes `manubot-bibliography-cache` and
  -- `manubot-output-bibliography` unconditionally. On a fresh checkout
  -- the conventional location is `_freeze/manubot-cache.json`, and
  -- `_freeze/` may not exist yet — the filter would then crash with
  -- FileNotFoundError before Quarto can render anything. Pre-create
  -- the parent directories so the first render is hands-off.
  local meta = doc.meta or {}
  ensure_parent_dir(pandoc.utils.stringify(meta["manubot-bibliography-cache"] or ""))
  ensure_parent_dir(pandoc.utils.stringify(meta["manubot-output-bibliography"] or ""))
  return pandoc.utils.run_json_filter(doc, "pandoc-manubot-cite")
end
