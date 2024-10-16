import streamlit as st
import pandas as pd
from io import BytesIO
import xlsxwriter

# Set the page configuration
st.set_page_config(
    page_title="Analytics Review Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Title of the app
st.title("Analytics Review Assistant")

# Description
st.markdown("""
Enter the **Most Recent Report End Date**, upload the client-specific dataset from Funnel, and click **Process File** to identify new Campaigns, Ad Sets, and Ads that have spent money after the specified date.
""")

# Sidebar for inputs
st.sidebar.header("Input Parameters")

# Date input
report_end_date = st.sidebar.date_input(
    "Most Recent Report End Date",
    value=pd.to_datetime("today"),
    help="Select the most recent report end date."
)

# File uploader
uploaded_file = st.sidebar.file_uploader(
    "Upload your dataset (CSV or Excel)",
    type=["csv", "xlsx"],
    help="Drag and drop your file here or click to select a file."
)

# Display an initial message if no file is uploaded
if uploaded_file is None:
    st.info("Please upload a CSV or Excel file using the sidebar to proceed.")

# Process button
if uploaded_file is not None and st.sidebar.button("Process File"):
    try:
        # Read the file based on its type
        if uploaded_file.type == "text/csv":
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        # Ensure necessary columns are present
        required_columns = ["Date", "Channel", "Media Source", "Campaign Name", "Campaign Name (Short)", "Ad Set", "Ad Name (Short)", "Cost (USD)"]
        if not all(col in df.columns for col in required_columns):
            st.error(f"Uploaded file must contain the following columns: {', '.join(required_columns)}")
        else:
            # Convert 'Date' column to datetime using the correct format
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

            # Filter out rows with invalid dates
            if df['Date'].isnull().any():
                st.warning("Some dates could not be parsed and will be ignored.")
            df = df.dropna(subset=['Date'])

            # Split data into before and after the report end date
            before_df = df[df['Date'] <= pd.to_datetime(report_end_date)]
            after_df = df[df['Date'] > pd.to_datetime(report_end_date)]

            # Identify unique Campaigns, Ad Sets, and Ads before the date
            existing_campaigns = set(before_df['Channel'] + "_" + before_df['Campaign Name (Short)'])
            existing_adsets = set(before_df['Ad Set'].unique())
            existing_ads = set(before_df['Ad Name (Short)'].unique())

            # Identify unique Campaigns, Ad Sets, and Ads after the date
            after_campaigns = set(after_df['Channel'] + "_" + after_df['Campaign Name (Short)'])
            after_adsets = set(after_df['Ad Set'].unique())
            after_ads = set(after_df['Ad Name (Short)'].unique())

            # Determine new entities
            new_campaigns = after_campaigns - existing_campaigns
            new_adsets = after_adsets - existing_adsets
            new_ads = after_ads - existing_ads

            # Prepare the DataFrame for display
            display_df = after_df[['Channel', 'Media Source', 'Campaign Name (Short)', 'Ad Set', 'Ad Name (Short)', 'Cost (USD)']].copy()

            # Mark new vs existing
            display_df['Campaign Status'] = display_df.apply(
                lambda x: "New" if (x['Channel'] + "_" + x['Campaign Name (Short)']) in new_campaigns else "Existing",
                axis=1
            )
            display_df['Ad Set Status'] = display_df['Ad Set'].apply(
                lambda x: "New" if x in new_adsets else "Existing"
            )
            display_df['Ad Status'] = display_df['Ad Name (Short)'].apply(
                lambda x: "New" if x in new_ads else "Existing"
            )

            # Filter to only include rows if there is at least one new item
            final_df = display_df[(display_df['Campaign Status'] == 'New') | 
                                  (display_df['Ad Set Status'] == 'New') | 
                                  (display_df['Ad Status'] == 'New')]

            # Rename columns for clarity BEFORE styling
            final_df = final_df.rename(columns={
                'Campaign Name (Short)': 'Campaign (Short)',
                'Ad Set': 'Ad Set',
                'Ad Name (Short)': 'Ad',
                'Campaign Status': 'Campaign Status',
                'Ad Set Status': 'Ad Set Status',
                'Ad Status': 'Ad Status'
            })

            # Rearrange columns based on new requirements
            final_df = final_df[['Media Source', 'Channel', 'Campaign Status', 'Campaign (Short)', 'Ad Set Status', 'Ad Set', 'Ad Status', 'Ad', 'Cost (USD)']]

            # Remove duplicates to list unique combinations
            final_df = final_df.drop_duplicates(subset=['Channel', 'Campaign (Short)', 'Ad Set', 'Ad'])

            # Define a function to apply richer color coding
            def color_status(val):
                if val == "New":
                    return 'background-color: #2e8b57; color: white'  # Dark green with white text
                else:
                    return 'background-color: #808080; color: white'  # Gray with white text

            # Apply styling after renaming
            styled_df = final_df.style.applymap(color_status, subset=['Campaign Status', 'Ad Set Status', 'Ad Status'])

            # Display the table using st.table
            st.subheader("New Campaigns, Ad Sets, and Ads After the Report End Date")
            st.markdown("""
            <style>
            .stTable thead th {
                background-color: #2e2e2e;  /* Darker header for better contrast */
                color: white;  /* White text for headers */
                font-size: 14px;  /* Increase header font size */
            }
            </style>
            """, unsafe_allow_html=True)
            st.table(styled_df)

            # Export to Excel with highlighting
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=False, sheet_name='New Entities')
                workbook = writer.book
                worksheet = writer.sheets['New Entities']

                # Define formats for highlighting
                new_format = workbook.add_format({'bg_color': '#2e8b57', 'font_color': 'white'})
                existing_format = workbook.add_format({'bg_color': '#808080', 'font_color': 'white'})

                # Apply highlighting to the corresponding columns
                for row_num, value in enumerate(final_df['Campaign Status'].values, start=1):
                    format_to_apply = new_format if value == "New" else existing_format
                    worksheet.write(row_num, 2, value, format_to_apply)
                for row_num, value in enumerate(final_df['Ad Set Status'].values, start=1):
                    format_to_apply = new_format if value == "New" else existing_format
                    worksheet.write(row_num, 4, value, format_to_apply)
                for row_num, value in enumerate(final_df['Ad Status'].values, start=1):
                    format_to_apply = new_format if value == "New" else existing_format
                    worksheet.write(row_num, 6, value, format_to_apply)

            output.seek(0)

            # Provide download link for the Excel file
            st.download_button(
                label="Download Results as Excel",
                data=output,
                file_name='new_ads_report.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

    except Exception as e:
        st.error(f"An error occurred while processing the file: {e}")

# Additional styling with CSS for better table appearance
st.markdown("""
<style>
table {
    width: 100%;
    border-collapse: collapse;
}
th, td {
    padding: 4px 8px;  /* Reduced padding to make text smaller */
    border: 1px solid #ddd;
    text-align: left;
}
th {
    background-color: #2e2e2e;  /* Darker header for better contrast */
    color: white;  /* White text for headers */
    font-size: 14px;  /* Increase header font size */
}
</style>
""", unsafe_allow_html=True)