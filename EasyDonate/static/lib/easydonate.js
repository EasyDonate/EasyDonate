function setupValues(form)
{
	form.on('inputadded', function(event, param){
		$("#"+param.id).blur(function(){
			var val = ($(this).val() == '') ? $(this).attr('id') : $(this).val();
			$(this).replaceWith('<label class="valuename" id="' + $(this).attr('id') + '">' + val + '</label>');
			$('#vhidden-'+param.id).val(val);
			form.trigger('labeladded', {id: $(this).attr('id')});
		});
	});
	form.on('labeladded', function(event, param){
		$("#"+param.id).click(function(){
			$(this).replaceWith('<input type="text" class="valuename" id="'+param.id+'" value="'+$("#"+param.id).text()+'"/>');
			$("#"+param.id).focus();
			$("#"+param.id).select();
			form.trigger('inputadded', {id: param.id});
		});
	});
}
function addValue(form)
{
	var count = $(form+" .valuename").length + 1;
	$(form+" > .valuetable tr:last").after("<tr><td><input type='text' class='valuename' id='vname-" + count + "'/></td> \
											<input type='hidden' id='vhidden-vname-"+count+"' name='vname-"+count+"'/> \
											<td><input type='text' class='value' name='value-" + count + "' id='value-" + count + "'/></td> \
											<td><a href='javascript:void(0)' onclick='removeValue(\"#value-"+count+"\")'>X</a></tr>");
	$("#vname-"+count).focus();
	$(form).trigger('inputadded', {id: 'vname-' + count});
}
function removeValue(value)
{
	$(value).closest('tr').remove();
}
function addField(form)
{
	var count = $(form+" .fieldname").length + 1;
	$(form+" > .fieldtable tr:last").after("<tr><td><input type='text' style='width:65%;' class='fieldname' name='fname-"+count+"' id='fname-"+count+"'/></td> \
											<td><a href='javascript:void(0)' onclick='removeValue(\"#fname-"+count+"\")'> \
											<img src=\"/static/css/img/edit-delete-4.png\" width=\"20\" height=\"20\"/></a></td></tr>");
	$('#fname-'+count).focus();
}
function confirmDelete(item, href)
{
	if(window.confirm("Are you sure you want to delete this " + item + "?"))
	{
		window.location = href;
	}
}