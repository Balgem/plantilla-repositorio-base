# Corpus de la campaña K7

Documentos que el bot usa como fuente para responder en el chat (RAG, Unidad 2.5). Los indexa `src/indexar_corpus.py`.

**Datos de ejemplo:** la campaña, la marca y el producto son ficticios. El precio (59.990 CLP), el link (`https://ejemplo.cl/r/k7`) y "sin descuentos" son los mismos de todo el proyecto; la ficha técnica, el despacho y la garantía se inventaron para tener un corpus con contenido. En una campaña real, estos archivos se reemplazan por el brief que entrega la marca.

Este README no se indexa. Cada archivo de `campana_k7/` trata **un solo tema**, en párrafos cortos que repiten el sujeto ("El despacho cuesta…", no "tiene un costo de…"), para que cada chunk se entienda solo.
