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

function Pandoc(doc)
  return pandoc.utils.run_json_filter(doc, "pandoc-manubot-cite")
end
