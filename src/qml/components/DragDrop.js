.pragma library

function readMimePath(dragOrDrop) {
    if (!dragOrDrop)
        return ""

    if (dragOrDrop.text)
        return dragOrDrop.text

    if (dragOrDrop.hasText)
        return dragOrDrop.text || ""

    var formats = dragOrDrop.formats
    if (formats && dragOrDrop.getDataAsString) {
        for (var i = 0; i < formats.length; i++) {
            if (formats[i] === "text/plain") {
                var plain = dragOrDrop.getDataAsString("text/plain")
                if (plain)
                    return plain
            }
        }
    }

    var source = dragOrDrop.source
    if (source) {
        if (source.rowPath)
            return source.rowPath
        if (source.itemPath)
            return source.itemPath
    }

    return ""
}

function acceptDrop(drop) {
    if (!drop)
        return
    if (drop.acceptProposedAction)
        drop.acceptProposedAction()
}
