General Steps to Export/Import

1. Login to Microsoft Graph https://developer.microsoft.com/en-us/graph/graph-explorer
2. Click on Resources and then search for Tasks
3. Execute the Tasks Get
4. If you get Internal Error, go to Modify Permissions, and Consent to Tasks read & Write
5. Run the Tasks Get again and ensure it works
6. Go to Access Token and copy it


Add Powershell to path
<code>export PATH=$PATH:/usr/local/Cellar/powershell-lts/7.2.9/libexec</code>


Export
1. Run the above general steps
2. In Powershell run the command ./my-to-do.ps1 backup
   <code>pwsh my-to-do.ps1 backup</code>
4. Paste the OAuth access token from the general section
5. A file named microsoft_todo_backup.xml will be created

Import

1. Run the above general steps for target account
2. In Powershell run the command ./my-to-do.ps1 restore
<code>pwsh my-to-do.ps1 restore</code>
4. Paste the OAuth access token from the general section
5. Tasks from the file named microsoft_todo_backup.xml will be imported into target account
6. Login and check the target account


References:
Rest APIs
https://learn.microsoft.com/en-us/graph/api/resources/todo-overview?view=graph-rest-1.0

Script Original:
https://blog.osull.com/2020/09/14/backup-migrate-microsoft-to-do-tasks-with-powershell-and-microsoft-graph/

Changes:
Changed beta to v1.0
Added parameters
