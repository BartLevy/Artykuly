import base64
import os
import uuid
import requests
import json,subprocess
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plot
import plotly.graph_objects as go
import plotly.express as px

class InfiReports:
    #def __init__(self):        
        
        #print("xxxxxxxx")

    def __init__(self, css_file = None):
        super().__init__()
        self.CHART_TYPE_BAR = 0
        self.CHART_TYPE_PIE = 1
        self.CHART_TYPE_POLAR = 2
        self.CHART_TYPE_LINE = 3
        self.reportHtml = ""
        self.customFont = ""
        self.header = "<html><head><meta charset='UTF-8' /></head><style>{style}</style><body>"
        self.footer = "<hr/><small>Raport wygenerowany: {dateTime}. </small></body></html>" #System WiseHub.pl.
        self.defaultCss = """@font-face {            
            font-family: 'Custom';
            src: url({customFont}) format('woff') }             
            body {width:1024px;font-family:Custom,'Courier New',Verdana,Arial;font-size:16px;line-height: 1.3em;} 
            pre {border: 20px solid #d7e8ee; width: fit-content;margin: 0 auto; padding: 20px 60px;}
            pre, table {font-family:Custom,'Courier New';font-size:13px;}
            table {width: 100%;}
            /*table tr:nth-child(odd) {background: #d7e8ee;}            */
            td {border-bottom:1px dotted gray}
            h1 {border:1px solid #1d3557; color:#1d3557; border-bottom-width: 3px; padding: 20px;line-height:1.2em;}
            h2 {border-bottom:1px dotted #1d3557; color:#1d3557;padding:20px 0px 10px 20px;}
            """

        self.cssFile = css_file
        	        
    def set_css(self, css_file):
        self.cssFile = css_file
    
    def set_custom_font(self, font_file):
        with open(font_file, "rb") as f:
            encoded_string = base64.b64encode(f.read())
            _, file_extension = os.path.splitext(font_file)
            file_extension = file_extension[1:]
            self.customFont = "data:font/{};charset=utf-8;base64,{}".format(file_extension, encoded_string.decode('utf-8'))
    
    def get_colors(self):            
        return [
            'tab:blue',
            'tab:orange',
            'tab:green',
            'tab:red',
            'tab:purple',
            'tab:brown',
            'tab:pink',
            'tab:gray',
            'tab:olive',
            'tab:cyan'
        ]

    def add_raw(self, html):
        self.reportHtml += html

    def get_bar_sensitive(self, percent):
        percent_round = int(round(percent,0) )
        col = "red"    
        if (percent_round>50) : col = "orange"
        if (percent_round>70) : col = "aquamarine"
        if (percent_round>90) : col = "green"
        html = f"<div style='padding:8px; width:100%;border:1px solid gray; box-sizing:border-box;'><div style='background-color:{col};border-right:1px solid {col};width:{percent_round}%'>&nbsp;</div></div>"
        return html
        
    def add_bar_sensitive(self, percent):
        self.add_raw(self.get_bar_sensitive(percent))


    def add_table(self, df, column_labels = None, sensitive_colum_idx = None):
        html = "<center><table>"
        if (column_labels==None): column_labels =  df.columns.tolist()
        html += "<tr>"                    
        for c in column_labels:
            html+=f"<td align='center' style='background-color:#f0f0ff;'><b>{c}</b></td>"
            
        html += "</tr>"

        for i in range(df.shape[0]):  # iterate over rows
            html += "<tr>"
            for j in range(df.shape[1]):  # iterate over columns
                v = df.iloc[i, j]
                align = ""
                if (not isinstance(v, str)): align = "align='right'"
                if isinstance(v, (float, np.number, int)):                     
                    if (j==sensitive_colum_idx):
                        align = "align='left' style='width:150px'"
                        v = self.get_bar_sensitive(v)
                    else:
                        v = f"{v:.2f}"

                html+=f"<td {align}>{v}</td>"
            html +="</tr>"
                      
        html += "</table></center>"
        self.add_raw(html)                 

    def break_page(self):
        self.add_raw("<p style='page-break-after: always;'> </p>")
    
    def add_h1(self, html):
        self.add_raw("<h1>{}</h1>".format(html))
    
    def add_h2(self, html):
        self.add_raw("<h2>{}</h2>".format(html))
    
    def add_h3(self, html):
        self.add_raw("<h3>{}</h3>".format(html))

    def add_pre(self, html):
        self.add_raw("<pre style='display: flex; justify-content: center;'>{}</pre>".format(html))
    
    def add_hr(self):
        self.add_raw("<hr/>")
    
    def add_p(self, html):
        self.add_raw("<p>{}</p>".format(html.replace("\n","<br/>")))
    
    def add_embeded_img(self, image_file_path, width_percent=100, delete_when_done = False):
        with open(image_file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read())
            _, file_extension = os.path.splitext(image_file_path)
            file_extension = file_extension[1:]

            base = "data:image/{};base64,{}".format(file_extension, encoded_string.decode('utf-8'))
            self.add_raw("<p style='text-align:center'><img src='{}' style='width:{}%'</p>".format(base, width_percent))
        if (delete_when_done):
            os.remove(image_file_path)


    def add_embeded_plot(self, plt, width_percent=100):
        fn = "plot_{}.png".format(str(uuid.uuid1()))
        if (hasattr(plt,'savefig')):
            plt.savefig(fn)
        else:
            fig = plt.get_figure()
            fig.savefig(fn)
        self.add_embeded_img(fn, width_percent, True)
        #os.remove(fn)
    


    def add_chart_with_series (self, array_of_series, width = 100):
        """
        go.Scatter(
        x=categories,
        y=values1,
        mode='lines+markers',  # Line with markers
        name='Series 1'
        ),"""
        fig = go.Figure(data=array_of_series)
            
        # Update layout with larger fonts
        fig.update_layout(
            width=700,  # Equivalent to figsize
            height=560,  # Equivalent to figsize
            legend=dict(
                title="",
                font=dict(size=10)  # Larger font for legend title
            ),
            margin=dict(b=100),  # Adjust bottom margin for better layout
            xaxis=dict(
                tickangle=-45,  # Rotate x-axis labels
                tickmode='array',
                tickvals=array_of_series[0].x,
                ticktext=array_of_series[0].x,
                #title=dict(text="Categories", font=dict(size=18)),  # Larger font for x-axis title
                tickfont=dict(size=10)  # Larger font for x-axis labels
            ),
            yaxis=dict(
                title=dict(text="Wartości", font=dict(size=12)),  # Larger font for y-axis title
                tickfont=dict(size=14)  # Larger font for y-axis labels
            )
        )
        fn = "plot_{}.png".format(str(uuid.uuid1()))
        fig.write_image(fn)
        self.add_embeded_img(fn, width, True)
    
    #mega ceikawe jak prosto: https://plotly.com/python/line-and-scatter/
    def add_chart(self, type, categories, values, width=100):
        def autopct_func(pct):
            return ('%1.1f%%' % pct) if pct >= 3 else ''
        
        if (type == self.CHART_TYPE_POLAR):
            values = list(values)
            
            num_vars = len(categories)            
            angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()        
          
            angles += angles[:1]
            values += values[:1]

            # Sprawdzenie długości tablic
            
            fig = plot.figure(figsize=(6,6))
            ax = fig.add_subplot(111, polar=True)
            ax.fill(angles, values, alpha=0.25, color='g')
            ax.plot(angles, values, color='g')

            # Ustawienie etykiet kategorii zamiast stopni
            ax.set_xticks(angles[:-1])  # Pomijamy ostatni kąt, który jest powtórzeniem pierwszego
            ax.set_xticklabels(categories)


            plot.grid(True)
            
           
            self.add_embeded_plot(plot, width_percent=width)

        if (type == self.CHART_TYPE_PIE):
            fig = go.Figure(data=[go.Pie(
                labels=categories,
                values=values,
                textinfo='none',  # Remove labels from the pie chart
                hoverinfo='label+percent',  # Show labels and percentage on hover
                #marker=dict(colors=px.colors.qualitative.Pastel),  # Optional: use custom colors
                sort=False,  # Keep the order of categories as is
                rotation=0,
                hole = 0.5
            )])

            # Update layout to position the legend
            fig.update_layout(
                showlegend=True,
                legend=dict(
                    x=1,  # Positioning the legend to the right of the chart
                    y=0.5,
                    font=dict(size=10)
                ),
                margin=dict(l=0, r=0, t=0, b=0),  # Tight layout
                width=1000,  # Width of the chart
                height=500,  # Height of the chart                

            )
            fn = "plot_{}.png".format(str(uuid.uuid1()))
            fig.write_image(fn)
            self.add_embeded_img(fn, width, True)

        if (type == self.CHART_TYPE_BAR or  type == self.CHART_TYPE_LINE):
            fig = None
            if (type == self.CHART_TYPE_BAR):
                fig = go.Figure(data=[go.Bar(
                    x=categories,
                    y=values
                )])
            else:
                fig = go.Figure(data=[go.Scatter(
                    x=categories,
                    y=values
                )])

            # Update layout
            fig.update_layout(
                width=1000,  # Equivalent to figsize
                height=600,  # Equivalent to figsize
                legend=dict(title="x"),  # Add legend title
                margin=dict(b=100),  # Adjust bottom margin for better layout
                xaxis=dict(
                    tickangle=-45,  # Rotate x-axis labels
                    tickmode='array',
                    tickvals=categories,
                    ticktext=categories,                    
                ),
                yaxis=dict(
                    title=dict(text="Values", font=dict(size=18)),  # Larger font for y-axis title
                    tickfont=dict(size=14)  # Larger font for y-axis labels
                )
            )
            fn = "plot_{}.png".format(str(uuid.uuid1()))
            fig.write_image(fn)
            self.add_embeded_img(fn, width, True)


        """
        if (type == self.CHART_TYPE_PIE +1):            
            fig, ax = plot.subplots(figsize=(14, 7))
            #plot.subplots_adjust(left=0.0, right=0.5) 
            ax.set_position([-0.4, 0.1, 0.5, 0.8]) 
            plot.tight_layout()
            
            wedges, texts, autotexts = ax.pie(
                values, 
                labels=None,  # Remove labels from pie chart
                colors=self.get_colors(),  
                rotatelabels=True, 
                autopct=autopct_func, 
                startangle=0, 
                pctdistance=1.1  # Adjust this value if needed
            )            
            # Add a legend with the categories and place it on the chart
            ax.legend(wedges, categories,   loc="center right", bbox_to_anchor=(0, 0.5),  fontsize="small")
            

            
        if (type==222):
            fig, ax = plot.subplots(figsize=(12, 12))
            plot.subplots_adjust(bottom=0.5) 
            plot.tight_layout()
            #plot.ylabel('Y-axis')
            #plot.legend()
            ax.pie(values, labels=categories, colors=self.get_colors(),  rotatelabels=True, autopct='%1.1f%%', startangle=0, pctdistance=20.85)
        

        if (type == self.CHART_TYPE_BAR):            
            fig, ax = plot.subplots(figsize=(10, 8))
            ax.bar(categories, values)            
            ax.legend("x")
            #plot.tight_layout()
            #plot.subplots_adjust(bottom=0.5) 
            plot.xticks(categories, rotation=45, ha='right')
        """

        #self.add_embeded_plot(plot, width_percent=width)

    def get_report_body(self):        
        css = self.defaultCss
        if (self.cssFile!=None):
            with open(self.cssFile, "r") as f:
                css += f.read()
        
        ready = self.header.replace("{style}", css).replace("{customFont}", self.customFont)
        ready += self.reportHtml
        ready += self.footer
        current_time = datetime.now()

        # Format the current time as per the desired format
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
        ready = ready.replace("{dateTime}", formatted_time)

        return ready


    def save_html(self, out_file_name = None):

        if (out_file_name==None):
            out_file_name = str(uuid.uuid1())+".html"
        
        ready = self.get_report_body()
        with open(out_file_name, "w", encoding='utf-8') as f:
            f.write(ready)
        
        return out_file_name
    

    def save_in_db(self, api_host, name, category, array_of_departments,  html_b64, pdf_b64 = None, docx_b64 = None):
        url = api_host + "/infi-api/generated-report/save-generated-report"
        obj = {
            "category": category,
            "name": name,
            "bodyHtmlB64": html_b64,
            "bodyPdfB64": pdf_b64,
            "bodyDocxB64": docx_b64,
            "departments": ";".join(array_of_departments)
        }
        env = {
            "subscribedReportData" : obj
        }
        json_resposne = requests.post(url, data = json.dumps(env)).json() #.encode("utf-8")
        print(json_resposne)


    def convert_to_pdf(self, api_host, clean_up = True):
        html_file = self.save_html()        
        out_file = html_file+".pdf"
        subprocess.run(["wkhtmltopdf","--quiet","--print-media-type","--background","--page-size","A4", html_file, out_file])
        with open(out_file, "rb") as f:
            pdf_file_b64 = base64.b64encode(f.read()).decode("UTF-8")            
        if (clean_up): 
            os.remove(out_file)
            os.remove(html_file)

        return pdf_file_b64

    def convert_and_save(self, api_host, name, category, array_of_departments, make_pdf=True, make_docx = True, clean_up = True):
        html_file = self.save_html()
        html_file_b64 =None
        with open(html_file, "r", encoding="utf-8") as f: html_file_b64 = base64.b64encode(f.read().encode("utf-8")).decode("UTF-8")
        pdf_file_b64 = None
        doc_file_b64 = None

        if (make_pdf):
            out_file = html_file+".pdf"
            subprocess.run(["wkhtmltopdf","--print-media-type","--background","--page-size","A4", html_file, out_file])
            with open(out_file, "rb") as f:
                pdf_file_b64 = base64.b64encode(f.read()).decode("UTF-8")
                with open("b64.txt", "w") as fw: fw.write(pdf_file_b64)
            if (clean_up): os.remove(out_file)

        if (make_docx):
            out_file = html_file+".docx"
            subprocess.run(["pandoc","-s", html_file, "-o",out_file])
            with open(out_file, "rb") as f:
                doc_file_b64 = base64.b64encode(f.read()).decode("UTF-8")
            if (clean_up): os.remove(out_file)
        
        if (clean_up): os.remove(html_file)

        self.save_in_db(api_host, name, category, array_of_departments, html_file_b64, pdf_file_b64, doc_file_b64 )

        #res['file_html'] = base64.b64encode(common.getFileContent(f).encode("utf-8")).decode("UTF-8")
#res['file_pdf'] = base64.b64encode(common.getFileBinContent(f+".pdf")).decode("UTF-8")

        


    """
    def save_in_db(self, infi_db, name, rights):
        ready = self.get_report_body()         
        res,msg = infi_db.execute_query(f"insert into Sys_SubscribedReportData (guid,category,name,roleToOpen, body_html)  values (uuid(),'{infi_db.add_slashes(name)}','{infi_db.add_slashes(name)}','{infi_db.add_slashes(rights)}','{infi_db.add_slashes(ready)}')")        

        return res
    """


    def pad_left(self, str, left, filler="&nbsp;"):
        if (len(str)>left):
            return str[:left]
        else:
            for a in range(left-len(str)):
                str = filler+str
        return str

    def pad_right(self, str, left, filler="&nbsp;"):
        if (len(str)>left):
            return str[:len]
        else:
            for a in range(left-len(str)):
                str = str + filler
        return str

    def get_spacer(self, len, filler="&nbsp;"):
        str = ""
        for a in range(len):
            str += filler
        return str
