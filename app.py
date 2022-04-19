import streamlit as st
import pandas as pd
from lareview import find_duplicate_userid

def main():

    st.subheader("Upload system logical access control file")
    # upload excel file
    file = st.file_uploader("Upload excel file", type=["xlsx", "csv"])
    if file is not None:
        # if file type is xlsx
        if file.name.endswith('.xlsx'):
        # get sheet names list from excel file
            xls = pd.ExcelFile(file)
            sheets = xls.sheet_names
            # choose sheet name and click button
            sheet_name = st.selectbox('Choose sheetname', sheets)
            # choose header row number and click button
            header_row = st.number_input('Choose header row',
                                            min_value=0,
                                            max_value=10,
                                            value=0)

            df = pd.read_excel(file, header=header_row, sheet_name=sheet_name)
        # if file type is csv
        elif file.name.endswith('.csv'):
            df = pd.read_csv(file)
        st.write(df.astype(str))
 
        cols = df.columns
        # input title
        # title = st.sidebar.text_input('Title')

        # select user id column
        hcols = st.sidebar.multiselect('User ID column', cols)

        if hcols==[]:
            st.sidebar.error('Please select user id column')
            return

       # select content columns
        dcols = st.sidebar.multiselect('Content column', cols)

        # select filter columns
        fcols = st.sidebar.multiselect('Filter column', cols)

        # get filter value list
        if fcols:
            fcol=fcols[0]
            fval=df[fcol].astype(str).unique()
            # choose filter value
            fval_select=st.sidebar.selectbox('Choose filter value',fval)
        else:
            fval_select=None

        # radio button to choose report type
        report_type = st.sidebar.radio('Choose file type', ('System LA list', 'HR employee list','HR departure list'))

    
        # initialize session state
        if 'dfla' not in st.session_state:
            st.session_state.dfla = pd.DataFrame()
            st.session_state.dfla_id = ''

        if 'dfcurrent' not in st.session_state:
            st.session_state.dfcurrent = pd.DataFrame()
            st.session_state.dfcurrent_id = ''

        if 'dfdeparture' not in st.session_state:
            st.session_state.dfdeparture = pd.DataFrame()
            st.session_state.dfdeparture_id = ''


        def savedf():
            if fcols:
                dffilter=df[df[fcol]==fval_select].reset_index(drop=True)
            else:
                dffilter=df
            allcols=hcols+dcols+fcols
            # filter duplicate column list
            allcols=list(set(allcols))
            
            if report_type == 'System LA list':
                # st.warning('This is a system LA list report')
                st.session_state.dfla=dffilter[allcols]
                st.session_state.dfla_id = hcols[0]
            
            if report_type == 'HR employee list':
                # st.warning('This is a HR employee list report')
                st.session_state.dfcurrent=dffilter[allcols]
                st.session_state.dfcurrent_id = hcols[0]
            
            if report_type=='HR departure list':
                st.session_state.dfdeparture=dffilter[allcols]
                st.session_state.dfdeparture_id = hcols[0]
    
        # click button to generate docx
        st.sidebar.button('Upload data', on_click=savedf)

        # if report_type == 'System LA list':
        dfla=st.session_state.dfla
        st.warning('system LA list report '+str(dfla.shape))
        st.write(dfla.astype(str))

        # if report_type == 'HR employee list':
        dfcurrent=st.session_state.dfcurrent
        st.warning('HR employee list report '+str(dfcurrent.shape))
        st.write(dfcurrent.astype(str))

        dfdeparture=st.session_state.dfdeparture
        st.warning('HR departure list report '+str(dfdeparture.shape))
        st.write(dfdeparture.astype(str))
        
        # continue if dfla, dfcurrent, dfdeparture are not empty
        if dfla.empty or dfcurrent.empty or dfdeparture.empty:
            st.sidebar.error('Please upload all data first')
            return
        
        # button to analysis
        if st.sidebar.button('Analysis'):
            # combine dfla and dfcurrent
            dfla_id=st.session_state.dfla_id
            dfcurrent_id=st.session_state.dfcurrent_id
            dflacurrent=pd.merge(dfla, dfcurrent, left_on=dfla_id,right_on=dfcurrent_id,how='left')

            # combine dfla and dfdeparture
            dfla_id=st.session_state.dfla_id
            dfdeparture_id=st.session_state.dfdeparture_id
            dfladeparture=pd.merge(dfla, dfdeparture, left_on=dfla_id,right_on=dfdeparture_id,how='inner')

            # get dflacurrent which dfcurrent_id is null
            dflacurrent_null=dflacurrent[dflacurrent[dfcurrent_id].isnull()]
            st.subheader('System LA not found in HR list')
            if dflacurrent_null.shape[0]>0:
                st.warning('System LA not found in HR list '+str(dflacurrent_null.shape))
                st.table(dflacurrent_null.astype(str))
                st.download_button(data=dflacurrent_null.to_csv(index=False),label='Download data',file_name='dflacurrent_null.csv')
            else:
                st.success('All System LA found in HR list ')

            # display dfladeparture
            st.subheader('System LA found in HR departure list')
            if dfladeparture.shape[0]>0:
                st.warning('System LA found in HR departure list '+str(dfladeparture.shape))
                st.table(dfladeparture.astype(str))
                st.download_button(data=dfladeparture.to_csv(index=False),label='Download data',file_name='dfladeparture.csv')
            else:
                st.success('No System LA found in HR departure list')

            # display duplicate userid
            st.subheader('Duplicate userid')
            userls=dfla[dfla_id].tolist()
            dupdict=find_duplicate_userid(userls)
            for key,value in dupdict.items():
                st.warning('Duplicate userid '+str(key)+' total '+str(len(value)))
                udfla=dfla[dfla.index.isin(value)]
                st.table(udfla.astype(str))
            

if __name__ == '__main__':
    main()