# Доступные MCP-инструменты

## <list_metadata_objects>
- purpose: Получение списка объектов метаданных конфигурации с возможностью фильтрации по типу и имени
- arguments:
  - metaType: string, Тип объекта метаданных
  - nameMask: string, Маска имени объекта. Проверяется на вхождение подстроки в имя или синоним объекта
  - maxItems: number, Максимальное количество возвращаемых результатов
- example:
  - MCP_CALL: {"tool":"toolName": "get_metadata_structure","arguments": {"metaType": "Catalogs","name": "Номенклатура"}}

  
## <get_metadata_structure>
- purpose: Получение структуры объекта метаданных (реквизиты, табличные части, измерения, ресурсы)
- arguments:
  - metaType: string, Тип объекта метаданных
  - name: string, Точное имя объекта метаданных (без учета регистра)
- example:
  - MCP_CALL: {"tool":"toolName": "get_metadata_structure","arguments": {"metaType": "Documents","name": "РеализацияТоваровУслуг"}}

  
## <custom_query>
- purpose: Текст произвольного запроса к БД на языке 1С
- arguments:
  - text: string, текст запроса к базе на языке 1С
- example:
  - MCP_CALL: {"tool":"toolName": "custom_query","arguments": {"text": "ВЫБРАТЬ Номенклатура.Наименование, Номенклатура.Код ИЗ Справочник.Номенклатура КАК Номенклатура"}}

  
