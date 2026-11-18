// Native macOS PDF renderer. No external packages, browser, or model requests.
// swift -module-cache-path /tmp/bica-swift-cache tools/render_research_pdf.swift \
//   docs/reports/data/pdf_data.json docs/reports/final/report.pdf /tmp/bica-pdf-preview
import Foundation
import AppKit
import CoreGraphics
import CoreText
import ImageIO
import PDFKit

let argv = CommandLine.arguments
guard argv.count >= 3 else {
    fatalError("Usage: render_research_pdf.swift input.json output.pdf [preview-directory]")
}
let data = try Data(contentsOf: URL(fileURLWithPath: argv[1]))
let report = try JSONSerialization.jsonObject(with: data) as! [String: Any]
let summaries = report["summaries"] as! [[String: Any]]
let labels = report["labels"] as! [String: String]
let methods = report["methods"] as! [String: String]
let profiles = ["4.1-mini", "5.4-nano-none", "5.4-nano-low", "5.4-mini-low", "6.1-sol-low", "6-astra-low"]
let datasets = ["personamem", "babilong", "goal_shift"]
let datasetLabels = ["personamem":"PersonaMem", "babilong":"BABILong", "goal_shift":"Смена цели"]
func string(_ v: Any?) -> String { v == nil || v is NSNull ? "" : String(describing:v!) }
func num(_ r: [String: Any], _ key: String) -> Double { (r[key] as? NSNumber)?.doubleValue ?? 0 }
func fmt(_ x: Double, _ digits: Int = 4) -> String { String(format:"%.*f",digits,x) }
func color(_ hex: String) -> CGColor {
    let n = UInt32(hex.replacingOccurrences(of:"#",with:""),radix:16)!
    return CGColor(red:CGFloat((n>>16)&255)/255,green:CGFloat((n>>8)&255)/255,blue:CGFloat(n&255)/255,alpha:1)
}
let ink = color("#20343e"), muted = color("#61717b"), rule = color("#dbe3e7")
let colors = ["summary":color("#246f86"),"reflexive":color("#bc6646"),"full_context":color("#448267"),"last_window":color("#87919a")]
func matches(_ pattern: String, _ text: String) -> [NSTextCheckingResult] {
    try! NSRegularExpression(pattern:pattern,options:[.dotMatchesLineSeparators]).matches(in:text,range:NSRange(text.startIndex...,in:text))
}
func sub(_ text: String, _ range: NSRange) -> String { String(text[Range(range,in:text)!]) }
func clean(_ text: String) -> String {
    var s = text.replacingOccurrences(of:"<[^>]*>",with:"",options:.regularExpression)
    for (a,b) in [("&amp;","&"),("&lt;","<"),("&gt;",">"),("&quot;","\""),("&#x27;","'"),("&#39;","'"),("&nbsp;"," ")] { s=s.replacingOccurrences(of:a,with:b) }
    return s.replacingOccurrences(of:"\\s+",with:" ",options:.regularExpression).trimmingCharacters(in:.whitespacesAndNewlines)
}

final class Renderer {
    var context: CGContext
    var width: CGFloat = 595.28
    var height: CGFloat = 841.89
    var y: CGFloat = 48
    var page = 0
    var opened = false
    var section = ""
    var landscape = false
    var starts: [(String, Int)] = []
    var anchorPages: [String: Int] = [:]
    let margin: CGFloat = 44
    var available: CGFloat { width-2*margin }
    init(_ path: String) {
        var box=CGRect(x:0,y:0,width:width,height:height)
        let meta = [kCGPDFContextTitle:"Сжатие контекстной памяти языковых моделей",
                    kCGPDFContextAuthor:"BICA Agent",
                    kCGPDFContextCreator:"Offline research report"] as CFDictionary
        context=CGContext(URL(fileURLWithPath:path) as CFURL,mediaBox:&box,meta)!
    }
    func attr(_ s: String, _ size: CGFloat, _ bold: Bool = false, _ serif: Bool = false, _ fill: CGColor? = nil) -> NSAttributedString {
        let font = CTFontCreateWithName((serif ? (bold ? "Georgia-Bold" : "Georgia") : (bold ? "Arial-BoldMT" : "ArialMT")) as CFString,size,nil)
        let para = NSMutableParagraphStyle()
        para.lineSpacing = size*0.23
        para.lineBreakMode = .byWordWrapping
        return NSAttributedString(string:s,attributes:[
            NSAttributedString.Key(kCTFontAttributeName as String):font,
            NSAttributedString.Key(kCTForegroundColorAttributeName as String):fill ?? ink,
            .paragraphStyle:para])
    }
    func textHeight(_ s: String, _ w: CGFloat, _ size: CGFloat, _ bold: Bool=false, _ serif: Bool=false) -> CGFloat {
        let fs=CTFramesetterCreateWithAttributedString(attr(s,size,bold,serif))
        return ceil(CTFramesetterSuggestFrameSizeWithConstraints(fs,CFRange(location:0,length:0),nil,CGSize(width:w,height:10000),nil).height)+4
    }
    func drawText(_ s: String, _ x: CGFloat, _ top: CGFloat, _ w: CGFloat, _ size: CGFloat=10.5, _ bold: Bool=false, _ serif: Bool=false, _ fill: CGColor?=nil) {
        let a=attr(s,size,bold,serif,fill)
        let fs=CTFramesetterCreateWithAttributedString(a)
        let hh=textHeight(s,w,size,bold,serif)+3
        let path=CGPath(rect:CGRect(x:x,y:height-top-hh,width:w,height:hh),transform:nil)
        let frame=CTFramesetterCreateFrame(fs,CFRange(location:0,length:0),path,nil)
        context.saveGState();context.textMatrix = .identity;CTFrameDraw(frame,context);context.restoreGState()
        let visible=CTFrameGetVisibleStringRange(frame)
        precondition(visible.length==a.length,"Clipped text on page \(page): \(s.prefix(60))")
    }
    func line(_ x: CGFloat, _ top: CGFloat, _ x2: CGFloat, _ top2: CGFloat, _ fill: CGColor=rule, _ thickness: CGFloat=0.6) {
        context.setStrokeColor(fill);context.setLineWidth(thickness)
        context.move(to:CGPoint(x:x,y:height-top));context.addLine(to:CGPoint(x:x2,y:height-top2));context.strokePath()
    }
    func rect(_ x: CGFloat,_ top: CGFloat,_ w: CGFloat,_ h: CGFloat,_ fill: CGColor) {
        context.setFillColor(fill);context.fill(CGRect(x:x,y:height-top-h,width:w,height:h))
    }
    func dot(_ x: CGFloat,_ top: CGFloat,_ radius: CGFloat,_ fill: CGColor,_ outline: CGColor?=nil) {
        let rect=CGRect(x:x-radius,y:height-top-radius,width:radius*2,height:radius*2)
        context.setFillColor(fill);context.fillEllipse(in:rect)
        if let stroke=outline { context.setStrokeColor(stroke);context.setLineWidth(1.3);context.strokeEllipse(in:rect) }
    }
    func endPage() {
        guard opened else{return}
        line(margin,height-37,width-margin,height-37)
        drawText("BICA Agent  ·  Исследование памяти LLM",margin,height-29,available-130,8,false,false,muted)
        drawText("Содержание",width-margin-115,height-29,80,8,false,false,color("#246f86"))
        drawText(String(page),width-margin-26,height-29,26,8,true,false,muted)
        context.endPDFPage();opened=false
    }
    func newPage(_ title: String, _ wide: Bool=false) {
        endPage()
        section=title;landscape=wide
        width=wide ? 841.89 : 595.28;height=wide ? 595.28 : 841.89
        var box=CGRect(x:0,y:0,width:width,height:height)
        let value=NSData(bytes:&box,length:MemoryLayout<CGRect>.size)
        context.beginPDFPage([kCGPDFContextMediaBox:value] as CFDictionary)
        page+=1;opened=true;y=48
        if !starts.contains(where: {$0.0==title}) {starts.append((title,page-1))}
        drawText("ИССЛЕДОВАНИЕ КОНТЕКСТНОЙ ПАМЯТИ  /  \(title)",margin,22,available,7.3,false,false,muted)
        line(margin,39,width-margin,39)
    }
    func ensure(_ h: CGFloat) {
        if y+h>height-52 {newPage(section,landscape)}
    }
    func paragraph(_ s: String, _ size: CGFloat=10.5,_ bold: Bool=false,_ serif: Bool=false,_ fill: CGColor?=nil,_ after: CGFloat=9) {
        guard !s.isEmpty else{return}
        let hh=textHeight(s,available,size,bold,serif)
        ensure(hh+after);drawText(s,margin,y,available,size,bold,serif,fill);y+=hh+after
    }
    func heading(_ s: String,_ main: Bool=false) {
        let size: CGFloat=main ? 28 : 18
        ensure(textHeight(s,available,size,false,true)+55)
        y+=main ? 13 : 8;paragraph(s,size,false,true,color("#153d4d"),11)
    }
    func table(_ headers:[String],_ rows:[[String]],_ widths:[CGFloat]?=nil,_ font:CGFloat=9,_ repeatTitle:String?=nil,_ rowAnchors:[Int:String]=[:]) {
        let ws=widths ?? Array(repeating:available/CGFloat(headers.count),count:headers.count)
        func rowHeight(_ cells:[String],_ bold:Bool)->CGFloat {
            max(24,zip(cells,ws).map{textHeight($0.0,$0.1-13,font,bold)+12}.max() ?? 24)
        }
        func renderRow(_ cells:[String],_ head:Bool,_ alternate:Bool) {
            let hh=rowHeight(cells,head)
            rect(margin,y,ws.reduce(0,+),hh,head ? color("#e9f0f3") : color(alternate ? "#f7f9fa":"#ffffff"))
            var x=margin
            for i in 0..<cells.count {
                drawText(cells[i],x+6,y+6,ws[i]-13,font,head,false,head ? color("#254858"):ink)
                x+=ws[i]
            }
            line(margin,y+hh,margin+ws.reduce(0,+),y+hh)
            y+=hh
        }
        ensure(rowHeight(headers,true)+50)
        renderRow(headers,true,false)
        for (i,row) in rows.enumerated() {
            let hh=rowHeight(row,false)
            precondition(hh<height-125,"A table row is longer than a page")
            if y+hh>height-53 {
                newPage(section,landscape)
                if let title=repeatTitle {paragraph(title,10,true,false,muted,7)}
                renderRow(headers,true,false)
            }
            if let anchor=rowAnchors[i] {anchorPages[anchor]=page-1}
            renderRow(row,false,i%2==1)
        }
        y+=12
    }
    func chart(_ kind:String) {
        let hh:CGFloat=kind=="accuracy" ? 285 : (kind=="context" ? 210 : (kind=="retrieval" ? 255 : 290))
        ensure(hh+32)
        let start=y
        if kind=="accuracy" {
            let left=margin+91, cw=(available-91)/3, span=cw-27
            for (j,dataset) in datasets.enumerated() {
                let x=left+CGFloat(j)*cw
                drawText(datasetLabels[dataset]!,x,start,span+20,10,true)
                for tick in [0.0,0.5,1.0] {
                    let xx=x+CGFloat(tick)*span
                    drawText("\(Int(tick*100))%",xx-8,start+15,27,8.0,false,false,muted)
                    line(xx,start+24,xx,start+246)
                }
                for (i,profile) in profiles.enumerated() {
                    let yy=start+37+CGFloat(i)*34
                    if j==0{drawText(labels[profile]!.replacingOccurrences(of:"GPT-",with:""),margin,yy,86,8.5)}
                    for (m,mode) in ["summary","reflexive"].enumerated() {
                        let item=summaries.first{string($0["profile"])==profile && string($0["dataset"])==dataset && string($0["mode"])==mode}
                        guard let s=item else{
                            if m==0{drawText("нет прогона",x+10,yy,span,8,false,false,muted)};continue
                        }
                        let yp=yy+CGFloat(m)*10
                        rect(x,yp,CGFloat(num(s,"accuracy"))*span,7,colors[mode]!)
                        let ci=s["wilson_95_ci"] as! [Double]
                        line(x+CGFloat(ci[0])*span,yp+3.5,x+CGFloat(ci[1])*span,yp+3.5,ink,0.6)
                        drawText("\(Int(num(s,"correct")))/\(Int(num(s,"n")))",x+span+3,yp-1,25,8.0)
                    }
                }
            }
            drawText("Summary",margin+91,start+254,90,8,true,false,colors["summary"])
            drawText("Reflexive",margin+175,start+254,90,8,true,false,colors["reflexive"])
        } else if kind=="retrieval" {
            let left=margin+116, cw=(available-116)/2, span=cw-48
            for (j,mode) in ["summary","reflexive"].enumerated() {
                let x=left+CGFloat(j)*cw
                drawText(methods[mode]!,x,start,span+45,10,true,false,colors[mode])
                for tick in [0.0,0.5,1.0] {
                    drawText("\(Int(tick*100))%",x+CGFloat(tick)*span-8,start+20,27,8.0,false,false,muted)
                }
                for (i,profile) in profiles.enumerated() {
                    let yy=start+43+CGFloat(i)*31
                    if j==0{drawText(labels[profile]!.replacingOccurrences(of:"GPT-",with:""),margin,yy-6,108,8)}
                    let s=summaries.first{string($0["profile"])==profile && string($0["dataset"])=="goal_shift" && string($0["mode"])==mode}!
                    let a=x+CGFloat(num(s,"correct_before_retrieval")/num(s,"n"))*span
                    let z=x+CGFloat(num(s,"accuracy"))*span
                    line(x,yy,x+span,yy);line(a,yy,z,yy,colors[mode]!,2.7)
                    dot(a,yy,3.2,CGColor(gray:1,alpha:1),colors[mode]);dot(z,yy,3.2,colors[mode]!)
                    drawText("\(Int(num(s,"correct_before_retrieval"))) → \(Int(num(s,"correct")))/\(Int(num(s,"n")))",x+span+7,yy-5,45,8.5)
                }
            }
            drawText("Пустая точка — до поиска; закрашенная — итог. При равенстве точки совпадают.",margin,start+235,available,8,false,false,muted)
        } else if kind=="context" {
            let groupW=available/5
            for (i,profile) in profiles.prefix(5).enumerated() {
                let x=margin+CGFloat(i)*groupW
                drawText(labels[profile]!.replacingOccurrences(of:"GPT-",with:""),x,start,groupW-4,8.8,true)
                for (j,mode) in ["last_window","summary","reflexive","full_context"].enumerated() {
                    let s=summaries.first{string($0["profile"])==profile && string($0["dataset"])=="personamem" && string($0["mode"])==mode}!
                    let bar=CGFloat(num(s,"accuracy"))*115,xx=x+CGFloat(j)*20
                    rect(xx,start+151-bar,14,bar,colors[mode]!)
                    drawText("\(Int(num(s,"correct")))",xx,start+137-bar,20,8,true)
                }
            }
            var x=margin
            for mode in ["last_window","summary","reflexive","full_context"] {
                drawText(methods[mode]!,x,start+168,available/4,8,true,false,colors[mode]);x+=available/4
            }
        } else {
            let left=margin+91, cw=(available-91)/3, span=cw-18
            for (j,dataset) in datasets.enumerated() {
                let x=left+CGFloat(j)*cw
                let values=summaries.filter{string($0["dataset"])==dataset && ["summary","reflexive"].contains(string($0["mode"]))}
                let maxVal=values.map{num($0,"cost_usd")/num($0,"n")}.max()!*1.18
                drawText(datasetLabels[dataset]!,x,start,cw-5,10,true)
                for tick in [0.0,0.5,1.0] {
                    let xx=x+CGFloat(tick)*span
                    line(xx,start+32,xx,start+239)
                    let labelX=xx-(tick==0 ? 2 : (tick==1 ? 27 : 14))
                    drawText("$"+fmt(maxVal*tick,3),labelX,start+18,36,8.0,false,false,muted)
                }
                for (i,profile) in profiles.enumerated() {
                    let yy=start+43+CGFloat(i)*33
                    if j==0 {drawText(labels[profile]!.replacingOccurrences(of:"GPT-",with:""),margin,yy,86,8.5)}
                    if !values.contains(where:{string($0["profile"])==profile}) {
                        drawText("нет прогона",x+12,yy,span,8,false,false,muted)
                    }
                    for (m,mode) in ["summary","reflexive"].enumerated() {
                        if let s=values.first(where:{string($0["profile"])==profile && string($0["mode"])==mode}) {
                            let bar=CGFloat((num(s,"cost_usd")/num(s,"n"))/maxVal)*span
                            rect(x,yy+CGFloat(m)*10,bar,7,colors[mode]!)
                        }
                    }
                }
            }
            drawText("Summary",left,start+254,90,8,true,false,colors["summary"])
            drawText("Reflexive",left+84,start+254,90,8,true,false,colors["reflexive"])
            drawText("Средняя стоимость, USD. Шкалы панелей различаются; префикс GPT опущен.",margin,start+274,available,8.3,false,false,muted)
        }
        y=start+hh+8
    }
    func renderSection(_ s:[String:Any]) {
        let id=string(s["id"]);newPage(string(s["title"]))
        let body=string(s["html"])
        for match in matches("<(h1|h2|p|table|figure)\\b[^>]*>.*?</\\1>",body) {
            let chunk=sub(body,match.range),tag=sub(body,match.range(at:1))
            if tag=="h1"{heading(clean(chunk),true)}
            else if tag=="h2"{heading(clean(chunk))}
            else if tag=="p" {
                let caption=chunk.contains("class=\"caption\"") || chunk.contains("class=\"eyebrow\"")
                let lead=chunk.contains("class=\"lead\"")
                paragraph(clean(chunk),caption ? 8.3 : (lead ? 12 : 10.5),false,false,caption ? muted:nil)
                if id=="overview" && lead {
                    y+=6
                    table(["Примеры","Прогоны","Модели","Расход с отладкой"],[["48","686","5","$27,88"]],nil,10.5)
                }
            } else if tag=="figure" {
                chart(id)
                let caption=matches("<figcaption[^>]*>(.*?)</figcaption>",chunk).first
                if let cap=caption {paragraph(clean(sub(chunk,cap.range(at:1))),8.1,false,false,muted,8)}
            } else if tag=="table" {
                let parsed=matches("<tr[^>]*>(.*?)</tr>",chunk).map{m in
                    matches("<t[hd][^>]*>(.*?)</t[hd]>",sub(chunk,m.range(at:1))).map{clean(sub(sub(chunk,m.range(at:1)),$0.range(at:1)))}
                }
                if !parsed.isEmpty {
                    var ws:[CGFloat]?=nil
                    if id=="methods" && parsed[0].count==3{ws=[75,available-126,51]}
                    if id=="methods" && parsed[0].count==4{ws=[91,126,157,available-374]}
                    if id=="accuracy"{ws=[155,115,115,available-385]}
                    if id=="metric" && parsed[0].first=="Профиль" {ws=[145,80,100,80,available-405]}
                    if id=="metric" && parsed[0].first=="Метод" {ws=[68,107,75,145,available-395]}
                    if id=="errors" && parsed[0].count==2 {ws=[available-80,80]}
                    if id=="errors" && parsed[0].count==3 {ws=[172,65,available-237]}
                    if id=="goals" {ws=[145,62,72,90,82,available-451]}
                    if id=="paired" {ws=[82,138,30,58,137,available-445]}
                    if id=="cost"{ws=[205,65,80,available-350]}
                    table(parsed[0],Array(parsed.dropFirst()),ws,9)
                }
            }
        }
    }
    func finish(){endPage();context.closePDF()}
}

let renderer=Renderer(argv[2])
for (index,section) in (report["sections"] as! [[String:Any]]).enumerated() {
    renderer.renderSection(section)
    // Reserve the contents page so all printed page numbers are final.
    if index==0 {renderer.newPage("Содержание")}
}
renderer.newPage("Приложение A · Все итоговые ответы",true)
renderer.heading("Все 686 итоговых ответов")
renderer.paragraph("Одна строка — один основной прогон. Сначала указан ответ модели, затем эталон. При смене цели это второй вопрос. ∅ — пустой ответ; «нет данных» — статус insufficient_data. Сохранённые вопросы и пояснения оценки находятся в приложении C, в HTML ID открывает карточку задачи. Стоимость округлена; точные значения и доступные вопросы есть в CSV.",9.5)
let rows=report["rows"] as! [[String:Any]]
let answerRows=rows.map{r->[String] in
    let correct=(r["correct"] as? Bool)==true
    let status=correct ? "Верно" : (string(r["answer_status"])=="insufficient_data" ? "Нет данных":"Неверно")
    return [string(r["id"]),labels[string(r["profile"])]!,methods[string(r["mode"])]!,
            string(r["answer"]).isEmpty ? "∅" : string(r["answer"]),string(r["target"]),status,fmt(num(r,"cost_usd"),5)]
}
var datasetAnchors:[Int:String]=[:]
var seenDatasets=Set<String>()
for (index,row) in rows.enumerated() {
    let dataset=string(row["dataset"])
    if seenDatasets.insert(dataset).inserted {datasetAnchors[index]=dataset}
}
renderer.table(["Пример","Модель и reasoning","Метод","Ответ","Эталон","Оценка","USD"],answerRows,[135,151,98,111,94,78,86],8.6,"Все 686 ответов · продолжение",datasetAnchors)
renderer.newPage("Приложение B · Локальные проверки",true)
renderer.heading("Локальные и демонстрационные ответы")
renderer.paragraph("Эти записи не входят в 686 основных платных прогонов. Mock содержит программно заданные ответы. Неудачные локальные прогоны показаны явно. Четыре показательные платные трассы уже представлены итоговыми строками в приложении A.",9.5)
let archive=(report["archived"] as! [[String:Any]]).filter{!string($0["run"]).contains("/cases/")}
let archiveRows=archive.map{r->[String] in
    let run=string(r["run"]).replacingOccurrences(of:"examples/",with:"")
    let error=r["error"] as? [String:Any]
    let answer=string(r["answer"]).isEmpty ? (string(r["answer_status"])=="insufficient_data" ? "Недостаточно данных" : "Остановка: "+string(error?["type"])) : string(r["answer"])
    return [run,string(r["mode"]),string(r["checkpoint"]),string(r["question"]).isEmpty ? "Остановка до вопроса":string(r["question"]),answer]
}
renderer.table(["Прогон","Метод","Этап","Вопрос","Ответ или остановка"],archiveRows,[180,66,35,266,206],8.7,"Локальные проверки · продолжение")
let contexts=report["contexts"] as! [[String:Any]]
for c in contexts where !string(c["question"]).isEmpty {
    renderer.newPage("Приложение C · Сохранённые вопросы")
    renderer.anchorPages["question:"+string(c["id"])]=renderer.page-1
    renderer.heading(string(c["id"]))
    if !string(c["first_question"]).isEmpty {renderer.paragraph("Первая цель: "+string(c["first_question"]),9.5)}
    renderer.paragraph("Вопрос: "+string(c["question"]),10.5,true)
    renderer.paragraph("Эталон: "+string(c["target"])+". Вопрос взят из сохранённой трассы, эталон — из платных сводок.",9.5)
    for excerpt in c["source_excerpt"] as! [[String:Any]] {
        renderer.paragraph("Фрагмент "+string(excerpt["source_id"])+": "+string(excerpt["text"]),9.5)
    }
    let values=rows.filter{string($0["id"])==string(c["id"])}.map{r->[String] in
        [labels[string(r["profile"])]!,methods[string(r["mode"])]!,
         string(r["answer"]).isEmpty ? "∅" : string(r["answer"]),string(r["answer_note"])]
    }
    renderer.table(["Модель","Метод","Ответ","Как понимать оценку"],values,[129,88,90,renderer.available-307],9,nil)
    renderer.paragraph("Источники точного вопроса:",9,true)
    for source in c["question_sources"] as! [String] {renderer.paragraph(source,8.5,false,false,muted,4)}
    if string(c["dataset"])=="babilong" {
        renderer.paragraph("В локальной и платной сериях совпадают ID, ревизия и SHA-256 исходного датасета. Это основание связать вопрос с платными ответами. Оценка самого ответа сохранена без изменения.",9,false,false,muted)
    }
}
renderer.newPage("Материалы и воспроизведение")
renderer.heading("Как найти отдельный ответ")
renderer.paragraph("HTML-версия содержит фильтры по модели, набору, методу и правильности. Нажатие на ID открывает карточку задачи с вопросом, эталоном, ответами моделей и пояснениями оценки. Выбранные строки можно выгрузить в CSV. Все 686 записей доступны в all_answers.csv и all_answers.json; вопросы и источники — в example_contexts.json.")
renderer.heading("Дополнительный анализ BABILong")
renderer.paragraph("В babilong_sensitivity.csv сохранены 200 индивидуальных записей с исходной оценкой, дополнительным результатом без начального артикля и категорией ответа. Правила, все сложные фразы и парные сравнения находятся в babilong_sensitivity.md и babilong_sensitivity.json. Это ретроспективный анализ; первичные оценки не заменены.")
renderer.heading("Промежуточные ответы")
renderer.paragraph("В электронное приложение включены \(string(report["stage_count"])) записи вызовов из доступных локальных и mock-журналов, а также четырёх показательных платных прогонов. В saved_stage_responses.json сохранены исходные запросы и ответы. Большинство полных платных трасс в клоне отсутствует. Эти трассы не реконструировались.")
renderer.heading("Что проверено при сборке")
renderer.paragraph("Состав заданий сверен с двумя протоколами. Все итоговые ответы повторно сопоставлены с сохранёнными эталонами. Числа верных ответов, стоимость групп и 9 683 уникальных идентификатора оплаченных запросов согласованы. Сумма — $27,87631429.")
renderer.paragraph("Это проверка опубликованных материалов. Она не подтверждает заново извлечение эталонов из исходных датасетов и не заменяет отсутствующие полные журналы. Исторические модульные тесты и полные аудиты при редактуре не запускались.")
renderer.heading("Версии данных")
renderer.paragraph("Основа — коммит 60aa0c4. Источники: examples/openai-20261101 и examples/openai-strong-20261101, а также архив локальных и показательных прогонов. Ревизии датасетов находятся в manifests, SHA-256 файлов сборки — в verification.json.")
renderer.paragraph("Редакция документации от 18 ноября 2026 года. Новые эксперименты и платные запросы не проводились. Исходные ответы, эталоны, промпты и протоколы не изменены.",9,false,false,muted)
renderer.finish()

// Add real PDF destinations after pagination, independently for each version.
typealias ContentsEntry = (title:String, page:Int)
func destination(_ doc:PDFDocument,_ index:Int)->PDFDestination {
    let page=doc.page(at:index)!
    return PDFDestination(page:page,at:CGPoint(x:44,y:page.bounds(for:.mediaBox).maxY-44))
}
func addNavigation(_ doc:PDFDocument,_ entries:[ContentsEntry],_ groupPages:[String:Int]=[:]) {
    let temp=FileManager.default.temporaryDirectory.appendingPathComponent("bica-contents-\(UUID().uuidString).pdf")
    defer {try? FileManager.default.removeItem(at:temp)}
    let toc=Renderer(temp.path)
    toc.page=1
    toc.newPage("Содержание")
    toc.heading("Содержание",true)
    toc.paragraph("Нажмите на название раздела или номер страницы. Закладки PDF также позволяют переходить между разделами.",10.5,false,false,muted,20)
    var links:[(CGRect,Int)]=[]
    var appendixHeading=false
    toc.paragraph("ОСНОВНАЯ ЧАСТЬ",8.5,true,false,muted,8)
    for entry in entries where entry.title != "Содержание" {
        if entry.title.hasPrefix("Приложение") && !appendixHeading {
            toc.y+=12
            toc.paragraph("ПРИЛОЖЕНИЯ И МАТЕРИАЛЫ",8.5,true,false,muted,8)
            appendixHeading=true
        }
        let top=toc.y
        let hh=max(29,toc.textHeight(entry.title,toc.available-50,11)+9)
        precondition(top+hh<toc.height-70,"Contents must fit on one page")
        toc.drawText(entry.title,toc.margin,top+3,toc.available-50,11,false,false,color("#246f86"))
        toc.drawText(String(entry.page+1),toc.width-toc.margin-27,top+3,27,11,true,false,color("#246f86"))
        toc.line(toc.margin,top+hh-2,toc.width-toc.margin,top+hh-2)
        links.append((CGRect(x:toc.margin,y:toc.height-top-hh,width:toc.available,height:hh),entry.page))
        toc.y+=hh
    }
    toc.finish()
    let tocDoc=PDFDocument(url:temp)!
    doc.removePage(at:1)
    doc.insert(tocDoc.page(at:0)!.copy() as! PDFPage,at:1)
    let contents=doc.page(at:1)!
    for (bounds,index) in links {
        let annotation=PDFAnnotation(bounds:bounds,forType:.link,withProperties:nil)
        annotation.border=PDFBorder();annotation.border!.lineWidth=0
        annotation.destination=destination(doc,index)
        contents.addAnnotation(annotation)
    }
    for index in 0..<doc.pageCount where index != 1 {
        let page=doc.page(at:index)!,box=page.bounds(for:.mediaBox)
        let link=PDFAnnotation(bounds:CGRect(x:box.width-44-118,y:8,width:86,height:19),forType:.link,withProperties:nil)
        link.border=PDFBorder();link.border!.lineWidth=0
        link.destination=destination(doc,1)
        page.addAnnotation(link)
    }
    let outline=PDFOutline()
    for (index,entry) in entries.enumerated() {
        let item=PDFOutline();item.label=entry.title;item.destination=destination(doc,entry.page)
        if entry.title.hasPrefix("Приложение A") {
            for dataset in datasets {
                if let page=groupPages[dataset] {
                    let child=PDFOutline();child.label=datasetLabels[dataset]!;child.destination=destination(doc,page)
                    item.insertChild(child,at:item.numberOfChildren)
                }
            }
        }
        if entry.title.hasPrefix("Приложение C") {
            for c in contexts where !string(c["question"]).isEmpty {
                if let page=groupPages["question:"+string(c["id"])] {
                    let child=PDFOutline();child.label=string(c["id"]);child.destination=destination(doc,page)
                    item.insertChild(child,at:item.numberOfChildren)
                }
            }
        }
        outline.insertChild(item,at:index)
    }
    doc.outlineRoot=outline
}

// Render the summary independently: its concise sections retain the main evidence.
let outputURL=URL(fileURLWithPath:argv[2])
let pdf=PDFDocument(url:outputURL)!
let briefURL=outputURL.deletingPathExtension().appendingPathExtension("summary.pdf")
let briefRenderer=Renderer(briefURL.path)
for (index,section) in (report["brief_sections"] as! [[String:Any]]).enumerated() {
    briefRenderer.renderSection(section)
    if index==0 {briefRenderer.newPage("Содержание")}
}
briefRenderer.finish()
let brief=PDFDocument(url:briefURL)!
let entries=renderer.starts.map{(title:$0.0,page:$0.1)}
addNavigation(pdf,entries,renderer.anchorPages)
addNavigation(brief,briefRenderer.starts.map{(title:$0.0,page:$0.1)})
try pdf.dataRepresentation()!.write(to:outputURL,options:.atomic)
try brief.dataRepresentation()!.write(to:briefURL,options:.atomic)
print("PDF pages: \(pdf.pageCount); summary: \(brief.pageCount). Contents links and bookmarks added.")

if argv.count>=4 {
    let dir=URL(fileURLWithPath:argv[3]);try FileManager.default.createDirectory(at:dir,withIntermediateDirectories:true)
    let doc=CGPDFDocument(URL(fileURLWithPath:argv[2]) as CFURL)!
    var thumbs:[CGImage]=[]
    for i in 1...doc.numberOfPages {
        let page=doc.page(at:i)!,box=page.getBoxRect(.mediaBox),scale:CGFloat=1.25
        let w=Int(box.width*scale),h=Int(box.height*scale)
        let ctx=CGContext(data:nil,width:w,height:h,bitsPerComponent:8,bytesPerRow:w*4,space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue)!
        ctx.setFillColor(CGColor(gray:1,alpha:1));ctx.fill(CGRect(x:0,y:0,width:w,height:h))
        ctx.scaleBy(x:scale,y:scale);ctx.drawPDFPage(page)
        let image=ctx.makeImage()!
        let dest=CGImageDestinationCreateWithURL(dir.appendingPathComponent(String(format:"page-%02d.png",i)) as CFURL,"public.png" as CFString,1,nil)!
        CGImageDestinationAddImage(dest,image,nil);CGImageDestinationFinalize(dest)
        thumbs.append(image)
    }
    let sheetW=1200,sheetH=1400,cellW=600,cellH=466
    for start in stride(from:0,to:thumbs.count,by:6) {
        let ctx=CGContext(data:nil,width:sheetW,height:sheetH,bitsPerComponent:8,bytesPerRow:sheetW*4,space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue)!
        ctx.setFillColor(color("#dbe3e7"));ctx.fill(CGRect(x:0,y:0,width:sheetW,height:sheetH))
        for j in 0..<min(6,thumbs.count-start) {
            let img=thumbs[start+j],scale=min(CGFloat(cellW-20)/CGFloat(img.width),CGFloat(cellH-20)/CGFloat(img.height))
            let w=CGFloat(img.width)*scale,h=CGFloat(img.height)*scale
            let x=CGFloat((j%2)*cellW)+(CGFloat(cellW)-w)/2
            let y=CGFloat(sheetH-(j/2+1)*cellH)+(CGFloat(cellH)-h)/2
            ctx.draw(img,in:CGRect(x:x,y:y,width:w,height:h))
        }
        let dest=CGImageDestinationCreateWithURL(dir.appendingPathComponent("contact-\(start/6+1).png") as CFURL,"public.png" as CFString,1,nil)!
        CGImageDestinationAddImage(dest,ctx.makeImage()!,nil);CGImageDestinationFinalize(dest)
    }
    print("Rendered \(doc.numberOfPages) pages and contact sheets")
}
