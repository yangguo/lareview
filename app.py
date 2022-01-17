import streamlit as st
import pandas as pd

from lareview import combine_df_id

def main():

    st.subheader("Upload system logical access control file")
    # upload excel file
    file = st.file_uploader("Upload excel file", type=["xlsx", "xls"])
    if file is not None:
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
        st.write(df.astype(str))
 
        cols = df.columns
        # input title
        # title = st.sidebar.text_input('Title')

        # select user id column
        hcols = st.sidebar.multiselect('User ID column', cols)

        # select content columns
        dcols = st.sidebar.multiselect('Content column', cols)

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
            if report_type == 'System LA list':
                # st.warning('This is a system LA list report')
                st.session_state.dfla=df[hcols+dcols]
                st.session_state.dfla_id = hcols[0]
            
            if report_type == 'HR employee list':
                # st.warning('This is a HR employee list report')
                st.session_state.dfcurrent=df[hcols+dcols]
                st.session_state.dfcurrent_id = hcols[0]
            
            if report_type=='HR departure list':
                st.session_state.dfdeparture=df[hcols+dcols]
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
            st.warning('System LA not found in HR list '+str(dflacurrent_null.shape))
            st.write(dflacurrent_null.astype(str))
            st.download_button(data=dflacurrent_null.to_csv(index=False),label='Download data',file_name='dflacurrent_null.csv')

            # display dfladeparture
            st.warning('System LA found in HR departure list '+str(dfladeparture.shape))
            st.write(dfladeparture.astype(str))
            st.download_button(data=dfladeparture.to_csv(index=False),label='Download data',file_name='dfladeparture.csv')
        

if __name__ == '__main__':
    main()